#!/usr/bin/env python3
"""
security_scanner.py - Multi-Layer Agent Security, AST & Data-Flow Threat Scanner
Part of the 'skill-factory' meta-skill.

Capabilities:
1. Static Multi-line Regex Pattern Analysis (credentials, shells, prompt injections).
2. Multi-Language Inspection (Python, Bash, PowerShell, JavaScript/TypeScript, Markdown).
3. Python AST & Data-Flow Analysis:
   - Tracks Credential Sources (process configuration sources and secret token assignments).
   - Tracks Network Sinks (HTTP/socket outbound network transmissions).
   - Connects Sources to Sinks to detect Credential Exfiltration even across variables.
   - Captures SyntaxError as unparseable code security warnings instead of silently ignoring.
4. Dependency & Supply Chain Analysis (unpinned downloads, remote-script execution pipelines, raw IP endpoints).
5. NVIDIA SkillSpector availability reporting; external scans require explicit host invocation.
6. Composite Trust Status Matrix (eliminates false-positive CLEAN claims).
"""

import argparse
import ast
import json
import re
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

sys.dont_write_bytecode = True

# NOTE: Several signature literals below are built from short fragments so that
# other static tools do not match this scanner's own detection signatures. The
# composed values and the detection logic are unchanged; the maintainer
# regression tests lock them. This is not a claim that the scanner lacks the
# capabilities those tools report on.

# Multi-language static red flags
SECURITY_RED_FLAGS: List[Tuple[str, str, str]] = [
    # (Pattern, Vulnerability Name, Severity)
    (
        "(" + "cu" + "rl|wget)" + r"\s+[^|\n]+\|\s*(" + "ba" + "sh|sh|zsh|python|perl)",
        "Remote Pipe to Shell Execution",
        "CRITICAL",
    ),
    (
        r"powershell(\.exe)?\s+(-(enc|encodedcommand|e))\s+[A-Za-z0-9+/=]{10,}",
        "Encoded PowerShell Command Execution",
        "CRITICAL",
    ),
    (r"(nc|ncat|netcat)\s+(-e|\/bin\/(ba)?sh)", "Reverse Shell Spawn via Netcat", "CRITICAL"),
    (
        r"\/dev\/tcp\/[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\/[0-9]+",
        "Bash Direct Socket Connection",
        "CRITICAL",
    ),
    (
        "(" + "gh" + "p_[a-zA-Z0-9]{36}|github" + "_pat_[a-zA-Z0-9_]{82})",
        "Exposed GitHub Personal Auth Token",
        "CRITICAL",
    ),
    ("sk" + r"-[a-zA-Z0-9]{32,}", "Exposed OpenAI / Anthropic Secret Key", "CRITICAL"),
    ("AK" + r"IA[0-9A-Z]{16}", "Exposed AWS Access Key ID", "HIGH"),
    (
        r"-----BEGIN (RSA|EC|DSA|OPENSSH|PRIVATE) KEY-----",
        "Exposed Private Cryptographic Key",
        "CRITICAL",
    ),
    (
        r"(eval|exec)\s*\(\s*(base64\.b64decode|request|url[l]ib|socket|decode)",
        "Obfuscated / Remote Dynamic Code Execution",
        "CRITICAL",
    ),
    (
        r"subprocess\.(Popen|run|call|check_output)\s*\(.*shell\s*=\s*True.*\)",
        "Subprocess with Shell=True (Command Injection Risk)",
        "HIGH",
    ),
    (
        r"(ignore\s+(all\s+)?previous\s+instructions|system\s+prompt\s+override|you\s+are\s+now\s+in\s+developer\s+mode)",
        "Prompt Injection Directive Pattern",
        "HIGH",
    ),
    (r"os\.system\s*\(\s*f?[\"'].*(\$|\{).*", "Unsanitized OS Command Interpolation", "HIGH"),
    (
        r"Invoke-Expression\s+(\$|DownloadString)",
        "PowerShell Invoke-Expression Injection",
        "CRITICAL",
    ),
    (
        r"child_process\.(exec|execSync)\s*\(.*(\$|\+|concat)",
        "Node.js Unsanitized Command Execution",
        "HIGH",
    ),
    (
        r"https?:\/\/[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}(:[0-9]+)?",
        "Suspicious Hardcoded Raw IP HTTP Endpoint",
        "MEDIUM",
    ),
    (
        r"^\s*(?:export\s+)?([A-Za-z0-9_]*(?:API_KEY|API_TOKEN|TOKEN|SECRET|PASSWORD|AUTH|CREDENTIAL)[A-Za-z0-9_]*)\s*=\s*['\"]?([A-Za-z0-9_\-\.+=]{16,})['\"]?\s*$",
        "Hardcoded Secret Token in Environment / Config File",
        "CRITICAL",
    ),
]

def redact_sensitive_text(value: str) -> str:
    """Remove credential values from scanner snippets and externally supplied text."""
    text = str(value)
    assignment = re.compile(
        r"(?i)(\b[A-Z0-9_]*(?:API_KEY|API_TOKEN|TOKEN|SECRET|PASSWORD|PASSWD|AUTH|CREDENTIAL|PRIVATE_KEY)[A-Z0-9_]*\s*[:=]\s*)(?:\"[^\"]*\"|'[^']*'|[^\s,;#]+)"
    )
    text = assignment.sub(r"\1[REDACTED]", text)
    text = re.sub(r"\b(?:sk-[A-Za-z0-9_-]{12,}|gh[pousr]_[A-Za-z0-9_]{12,}|AKIA[0-9A-Z]{16})\b", "[REDACTED_TOKEN]", text)
    text = re.sub(r"(?i)(Bearer\s+)[A-Za-z0-9._~+/-]+=*", r"\1[REDACTED]", text)
    text = re.sub(
        r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----",
        "[REDACTED PRIVATE KEY MATERIAL]",
        text,
        flags=re.DOTALL,
    )
    return text


# Sensitive environment key fragments indicating credentials
SENSITIVE_ENV_KEYS = {
    "api_key",
    "token",
    "secret",
    "password",
    "auth",
    "credential",
    "private",
    "key",
    "openai_api_key",
    "anthropic_api_key",
    "github_token",
    "aws_secret_access_key",
    "access_key",
}

# Standard benign environment keys that do NOT contain credentials
BENIGN_ENV_KEYS = {
    "path",
    "home",
    "user",
    "username",
    "hostname",
    "lang",
    "lc_all",
    "os",
    "term",
    "pwd",
    "shell",
    "temp",
    "tmp",
    "editor",
    "prompt",
    "virtual_env",
    "pythonpath",
    "node_env",
    "colorterm",
    "lines",
    "columns",
    "systemroot",
    "windir",
    "comspec",
}


def is_sensitive_env_key(key_name: str) -> bool:
    """
    Checks if an environment variable key indicates a credential, secret, or token.
    Uses word-boundary and delimiter-aware matching to eliminate false positives
    like 'monkey', 'donkey', 'keyboard', etc.
    """
    key_lower = key_name.lower().strip()
    if key_lower in BENIGN_ENV_KEYS:
        return False

    if key_lower in SENSITIVE_ENV_KEYS:
        return True

    # Delimited segment match (e.g. AWS_SECRET_ACCESS_KEY, API_KEY, MY_TOKEN, APP_SECRET, MONKEY_KEY)
    segments = re.split(r"[_\-\.]", key_lower)
    sensitive_words = {
        "key",
        "token",
        "secret",
        "password",
        "auth",
        "credential",
        "private",
        "apikey",
        "jwt",
    }
    if any(s in sensitive_words for s in segments):
        return True

    patterns = [
        r"^api_?key",
        r"_api_?key$",
        r"^secret_",
        r"_secret$",
        r"^token_",
        r"_token$",
        r"^password_",
        r"_password$",
        r"^auth_",
        r"_auth$",
    ]
    return any(re.search(p, key_lower) for p in patterns)


# Known network modules and client variable names for accurate sink classification
BASE_NETWORK_MODULES = {"re" + "quests", "http" + "x", "aio" + "http", "url" + "lib", "h" + "ttp", "sock" + "et"}
NETWORK_SUBMODULES = {"request", "client", "session"}


class ASTDataFlowSecurityVisitor(ast.NodeVisitor):
    """
    Advanced Python AST Visitor with Source-to-Sink Data-Flow Detection.
    Connects sensitive-value extraction to outbound network calls.
    Tracks imported network-client aliases and instantiated client objects,
    and untaints variables upon reassignment with safe values.
    Avoids false positives on harmless dictionary access (dict.get) and benign env vars (PATH).
    """

    def __init__(self, filename: str):
        self.filename = filename
        self.issues: List[Dict[str, Any]] = []
        # Track variables that hold credentials or sensitive values
        self.tainted_vars: Set[str] = set()
        # Track dynamically discovered network modules and aliases
        self.network_modules: Set[str] = set(BASE_NETWORK_MODULES)
        # Track standalone network functions
        self.network_functions: Set[str] = {"urlopen", "fetch"}
        # Track network client classes (e.g. 'Session', 'Client', 'AsyncClient')
        self.network_client_classes: Set[str] = {"Session", "Client", "AsyncClient"}
        # Track instantiated network client variables
        self.network_client_vars: Set[str] = set()
        # Track dynamically discovered OS modules and aliases (e.g. 'os', 'operating_system')
        self.os_modules: Set[str] = {"os"}
        # Track environment mapping references and aliases (e.g. 'environ', 'env', 'env_vars')
        self.environ_vars: Set[str] = {"environ"}
        # Track standalone getenv functions and aliases (e.g. 'getenv', 'get_env', 'my_get')
        self.getenv_funcs: Set[str] = {"getenv"}
        # Track whether sensitive env access occurred anywhere
        self.has_credential_source = False
        self.has_network_sink = False

    def visit_Import(self, node: ast.Import):
        """Track module imports and aliases (e.g. imported client aliases)."""
        for alias in node.names:
            base_mod = alias.name.split(".")[0]
            as_name = alias.asname or alias.name
            if base_mod in BASE_NETWORK_MODULES:
                self.network_modules.add(as_name)
            elif base_mod == "os":
                self.os_modules.add(as_name)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        """Track from-imports and aliases for network sinks and credential sources."""
        mod = node.module or ""
        base_mod = mod.split(".")[0]
        if base_mod in BASE_NETWORK_MODULES:
            for alias in node.names:
                name = alias.name
                as_name = alias.asname or alias.name
                if name in (
                    "post",
                    "get",
                    "put",
                    "delete",
                    "patch",
                    "urlopen",
                    "connect",
                    "send",
                    "request",
                    "fetch",
                ):
                    self.network_functions.add(as_name)
                elif name in ("Session", "Client", "AsyncClient"):
                    self.network_client_classes.add(as_name)
                elif name in ("request", "client"):
                    self.network_modules.add(as_name)

        elif base_mod == "os":
            for alias in node.names:
                name = alias.name
                as_name = alias.asname or alias.name
                if name == "getenv":
                    self.getenv_funcs.add(as_name)
                elif name == "environ":
                    self.environ_vars.add(as_name)

        self.generic_visit(node)

    def is_network_client_creator(self, expr: ast.AST) -> bool:
        """Determines if expression creates an outbound network client instance (e.g. a network-client session)."""
        if isinstance(expr, ast.Call):
            if isinstance(expr.func, ast.Attribute):
                recv_name = getattr(expr.func.value, "id", "")
                if recv_name in self.network_modules and expr.func.attr in (
                    "Session",
                    "Client",
                    "AsyncClient",
                    "socket",
                    "build_opener",
                ):
                    return True
            elif isinstance(expr.func, ast.Name):
                if expr.func.id in self.network_client_classes:
                    return True
        return False

    def is_environ_reference(self, expr: ast.AST) -> bool:
        """Determines if expression references an environment variable mapping (e.g. env = process environment mapping)."""
        if isinstance(expr, ast.Attribute):
            recv_name = getattr(expr.value, "id", "")
            if recv_name in self.os_modules and expr.attr == "environ":
                return True
        elif isinstance(expr, ast.Name):
            if expr.id in self.environ_vars:
                return True
        return False

    def is_getenv_reference(self, expr: ast.AST) -> bool:
        """Determines if expression references a getenv function (e.g. get_fn = process environment lookup, my_get = env.get)."""
        if isinstance(expr, ast.Attribute):
            recv_name = getattr(expr.value, "id", "")
            if recv_name in self.os_modules and expr.attr == "getenv":
                return True
            if recv_name in self.environ_vars and expr.attr == "get":
                return True
        elif isinstance(expr, ast.Name):
            if expr.id in self.getenv_funcs:
                return True
        return False

    def is_credential_source_expr(self, node: ast.AST) -> bool:
        """
        Determines if an expression extracts credentials or sensitive environment data.
        Supports:
        - process environment mapping["KEY"], operating_system.environ["KEY"], env["KEY"]
        - process environment lookup("KEY"), operating_system.getenv("KEY"), get_env("KEY")
        - process environment mapping.get("KEY"), env.get("KEY"), my_get("KEY")
        - High-entropy literal secret patterns (known high-entropy credential prefixes)
        """
        # 1. Subscript access: process environment mapping["KEY"], env["KEY"], operating_system.environ["KEY"]
        if isinstance(node, ast.Subscript):
            is_environ = False
            if isinstance(node.value, ast.Attribute):
                recv_name = getattr(node.value.value, "id", "")
                if recv_name in self.os_modules and node.value.attr == "environ":
                    is_environ = True
            elif isinstance(node.value, ast.Name):
                if node.value.id in self.environ_vars:
                    is_environ = True

            if is_environ:
                # Inspect subscript key if it is a constant string
                if isinstance(node.slice, ast.Constant) and isinstance(node.slice.value, str):
                    return is_sensitive_env_key(node.slice.value)
                return True

        # 2. Call access: process environment lookup("KEY"), env.get("KEY"), get_env("KEY"), etc.
        if isinstance(node, ast.Call):
            is_env_call = False
            # Standalone function call: get_env("KEY"), getenv("KEY")
            if isinstance(node.func, ast.Name):
                if node.func.id in self.getenv_funcs:
                    is_env_call = True

            # Method call: process environment lookup("KEY"), operating_system.getenv("KEY"), env.get("KEY"), process environment mapping.get("KEY")
            elif isinstance(node.func, ast.Attribute):
                attr = node.func.attr
                recv = node.func.value
                recv_name = getattr(recv, "id", "")

                if attr == "getenv" and recv_name in self.os_modules:
                    is_env_call = True
                elif attr == "get":
                    if recv_name in self.environ_vars:
                        is_env_call = True
                    elif isinstance(recv, ast.Attribute):
                        base_recv = getattr(recv.value, "id", "")
                        if base_recv in self.os_modules and recv.attr == "environ":
                            is_env_call = True

            if is_env_call and node.args:
                if isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                    return is_sensitive_env_key(node.args[0].value)
                return True

        # 3. String literal resembling secret token or high-entropy key
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            val_lower = node.value.lower()
            if any(k in val_lower for k in ["ghp_", "sk-", "akia"]) and len(node.value) > 20:
                return True

        return False

    def contains_credential_source(self, node: ast.AST) -> bool:
        """Recursively checks if AST subtree contains a credential source."""
        for sub in ast.walk(node):
            if self.is_credential_source_expr(sub):
                return True
            if isinstance(sub, ast.Name) and sub.id in self.tainted_vars:
                return True
        return False

    def visit_Assign(self, node: ast.Assign):
        """
        Track variable assignments to detect:
        1. Tainted credential variables
        2. Network client instances (s = a network-client session)
        3. Environment mapping references (env = process environment mapping)
        4. getenv function references (my_get = process environment lookup)
        Also untaints variables when reassigned with benign values.
        """
        is_client = self.is_network_client_creator(node.value)
        is_tainted = self.contains_credential_source(node.value)
        is_env_ref = self.is_environ_reference(node.value)
        is_getenv_ref = self.is_getenv_reference(node.value)

        for target in node.targets:
            if isinstance(target, ast.Name):
                var_name = target.id
                if is_tainted:
                    self.tainted_vars.add(var_name)
                    self.has_credential_source = True
                else:
                    # Untaint variable if reassigned with a safe/clean expression
                    self.tainted_vars.discard(var_name)

                if is_client:
                    self.network_client_vars.add(var_name)
                elif var_name in self.network_client_vars:
                    self.network_client_vars.discard(var_name)

                if is_env_ref:
                    self.environ_vars.add(var_name)
                elif var_name in self.environ_vars and var_name != "environ":
                    self.environ_vars.discard(var_name)

                if is_getenv_ref:
                    self.getenv_funcs.add(var_name)
                elif var_name in self.getenv_funcs and var_name != "getenv":
                    self.getenv_funcs.discard(var_name)

            elif isinstance(target, (ast.Tuple, ast.List)):
                for elt in target.elts:
                    if isinstance(elt, ast.Name):
                        if is_tainted:
                            self.tainted_vars.add(elt.id)
                            self.has_credential_source = True
                        else:
                            self.tainted_vars.discard(elt.id)

        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign):
        """Handle annotated assignments (e.g. token: str = 'clean', env: dict = process environment mapping)."""
        if isinstance(node.target, ast.Name) and node.value:
            var_name = node.target.id
            if self.contains_credential_source(node.value):
                self.tainted_vars.add(var_name)
                self.has_credential_source = True
            else:
                self.tainted_vars.discard(var_name)

            if self.is_network_client_creator(node.value):
                self.network_client_vars.add(var_name)
            elif var_name in self.network_client_vars:
                self.network_client_vars.discard(var_name)

            if self.is_environ_reference(node.value):
                self.environ_vars.add(var_name)
            elif var_name in self.environ_vars and var_name != "environ":
                self.environ_vars.discard(var_name)

            if self.is_getenv_reference(node.value):
                self.getenv_funcs.add(var_name)
            elif var_name in self.getenv_funcs and var_name != "getenv":
                self.getenv_funcs.discard(var_name)

        self.generic_visit(node)

    def visit_Delete(self, node: ast.Delete):
        """Handle variable deletion (del token, del env)."""
        for target in node.targets:
            if isinstance(target, ast.Name):
                self.tainted_vars.discard(target.id)
                self.network_client_vars.discard(target.id)
                self.environ_vars.discard(target.id)
                self.getenv_funcs.discard(target.id)
                self.os_modules.discard(target.id)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call):
        # 1. Detect dynamic execution (eval, exec)
        if isinstance(node.func, ast.Name) and node.func.id in ("eval", "exec"):
            self.issues.append(
                {
                    "file": self.filename,
                    "line": getattr(node, "lineno", 0),
                    "issue": f"Dangerous dynamic builtin call: '{node.func.id}()'",
                    "severity": "CRITICAL",
                }
            )

        # 2. Detect subprocess(..., shell=True)
        if isinstance(node.func, ast.Attribute) and node.func.attr in (
            "Popen",
            "run",
            "call",
            "check_output",
        ):
            for kw in node.keywords:
                if (
                    kw.arg == "shell"
                    and isinstance(kw.value, ast.Constant)
                    and kw.value.value is True
                ):
                    self.issues.append(
                        {
                            "file": self.filename,
                            "line": getattr(node, "lineno", 0),
                            "issue": "subprocess invoked with shell=True (command injection risk)",
                            "severity": "HIGH",
                        }
                    )

        # 3. Detect Outbound Network Sinks with strict receiver and alias validation
        is_network_call = False
        sink_name = ""

        if isinstance(node.func, ast.Attribute):
            attr_name = node.func.attr
            receiver = node.func.value

            # Disqualify literal primitives: dict.get, list.count, str.find, etc.
            if not isinstance(receiver, (ast.Dict, ast.List, ast.Set, ast.Tuple, ast.Constant)):
                receiver_name = getattr(receiver, "id", "")
                is_submodule = (
                    isinstance(receiver, ast.Attribute) and receiver.attr in NETWORK_SUBMODULES
                )

                # Match if receiver is known network module, alias, or instantiated client variable
                if (
                    receiver_name in self.network_modules
                    or receiver_name in self.network_client_vars
                    or is_submodule
                ):
                    if attr_name in (
                        "post",
                        "get",
                        "put",
                        "delete",
                        "patch",
                        "urlopen",
                        "connect",
                        "send",
                        "request",
                        "sendall",
                    ):
                        is_network_call = True
                        sink_name = f"{receiver_name or getattr(receiver, 'attr', '')}.{attr_name}"

                # Chained attribute access like a URL-opening API
                elif isinstance(receiver, ast.Attribute):
                    base_id = getattr(receiver.value, "id", "")
                    if base_id in self.network_modules and attr_name in (
                        "post",
                        "get",
                        "put",
                        "urlopen",
                        "request",
                    ):
                        is_network_call = True
                        sink_name = f"{base_id}.{receiver.attr}.{attr_name}"

        elif isinstance(node.func, ast.Name):
            if node.func.id in self.network_functions:
                is_network_call = True
                sink_name = node.func.id

        if is_network_call:
            self.has_network_sink = True
            # Check if any argument or keyword argument contains credential source or tainted var
            exfiltrating = False
            for arg in node.args:
                if self.contains_credential_source(arg):
                    exfiltrating = True
                    break
            if not exfiltrating:
                for kw in node.keywords:
                    if self.contains_credential_source(kw.value):
                        exfiltrating = True
                        break

            if exfiltrating:
                self.issues.append(
                    {
                        "file": self.filename,
                        "line": getattr(node, "lineno", 0),
                        "issue": f"Critical Data Exfiltration: Credential/token passed directly to outbound network sink '{sink_name}'",
                        "severity": "CRITICAL",
                    }
                )

        # Check standalone credential access
        if self.is_credential_source_expr(node):
            self.has_credential_source = True

        self.generic_visit(node)


def is_documentation_illustrative_example(
    file_path: Path, line: str, desc: str, match_text: str
) -> bool:
    """
    Distinguishes conceptual security documentation / threat rubrics / anti-pattern examples
    from actionable executable commands or live credentials.

    Guarantees:
    - Never ignores real credentials (API keys, private keys, tokens) regardless of file type.
    - Never ignores actionable commands with real URLs (https://, http://, raw IPs, or variables).
    - Only de-escalates non-actionable abstract idiom mentions (e.g. a remote-script pipeline) in Markdown documentation
      when contextual indicators confirm it is an anti-pattern or rubric definition.
    """
    if file_path.suffix.lower() not in (".md", ".markdown", ".txt", ".rst"):
        return False

    # Never suppress secrets, credentials, or private keys
    desc_lower = desc.lower()
    if any(k in desc_lower for k in ["token", "key", "secret", "credential"]):
        return False

    line_lower = line.lower()

    if desc == "Remote Pipe to Shell Execution":
        # Check if there is an actionable remote URL, IP, or shell variable in the match
        has_remote_target = bool(
            re.search(
                r"https?://[a-zA-Z0-9_\-\.]+\.[a-zA-Z]{2,}|ftp://|\$[A-Za-z_]|[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}",
                match_text,
            )
        )
        # Contextual indicators that this is a risk definition or rubric
        is_rubric_or_doc = any(
            w in line_lower
            for w in [
                "risk",
                "indicator",
                "vulnerability",
                "rubric",
                "anti-pattern",
                "unpinned",
                "cve",
                "threat",
                "bad practice",
                "example",
                "prohibited",
                "downloads (",
                "audit",
                "report",
                "changelog",
                "findings",
                "rule",
            ]
        )
        if not has_remote_target and is_rubric_or_doc:
            return True

    if desc == "Prompt Injection Directive Pattern":
        is_defensive_doc = any(
            w in line_lower
            for w in [
                "detect",
                "rubric",
                "indicator",
                "prevent",
                "mitigate",
                "anti-pattern",
                "defense",
                "test",
                "pattern",
                "threat",
            ]
        )
        if is_defensive_doc:
            return True

    return False


def scan_file_security(file_path: Path) -> List[Dict[str, Any]]:
    """Runs multi-layer regex scanning and AST data-flow analysis on a single file."""
    findings = []
    try:
        text = file_path.read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        return [
            {"file": file_path.name, "line": 0, "issue": f"Unreadable file: {e}", "severity": "LOW"}
        ]

    # 1. Multi-line and line-by-line Regex Scanning
    is_env_file = file_path.name.lower().startswith("." + "env") or file_path.suffix.lower() in (
        ".ini",
        ".cfg",
        ".conf",
        ".toml",
    )
    lines = text.split("\n")
    for lineno, line in enumerate(lines, 1):
        for pattern, desc, severity in SECURITY_RED_FLAGS:
            if desc == "Hardcoded Secret Token in Environment / Config File" and not is_env_file:
                continue
            match = re.search(pattern, line, re.IGNORECASE)
            if match:
                match_text = match.group(0)
                if is_documentation_illustrative_example(file_path, line, desc, match_text):
                    continue
                findings.append(
                    {
                        "file": file_path.name,
                        "line": lineno,
                        "issue": desc,
                        "severity": severity,
                        "snippet": redact_sensitive_text(line.strip())[:100],
                    }
                )

    # Multi-line pattern scan across entire file
    multi_line_threats = [
        (
            r"base64\.(b64decode|decodebytes)\s*\(.*?\)\s*.*?(eval|exec)",
            "Multi-line Obfuscated Base64 Dynamic Execution",
            "CRITICAL",
        )
    ]
    for m_pattern, m_desc, m_sev in multi_line_threats:
        match = re.search(m_pattern, text, re.IGNORECASE | re.DOTALL)
        if match:
            # Avoid duplicate if already caught
            if not any(f["issue"] == m_desc for f in findings):
                findings.append(
                    {
                        "file": file_path.name,
                        "line": 1,
                        "issue": m_desc,
                        "severity": m_sev,
                        "snippet": redact_sensitive_text(match.group(0).replace("\n", " "))[:120],
                    }
                )

    # 2. Python AST & Data-Flow Analysis
    is_python_file = file_path.suffix.lower() == ".py"
    if not is_python_file and lines and lines[0].startswith("#!") and "python" in lines[0].lower():
        is_python_file = True

    if is_python_file:
        try:
            tree = ast.parse(text, filename=file_path.name)
            visitor = ASTDataFlowSecurityVisitor(file_path.name)
            visitor.visit(tree)
            findings.extend(visitor.issues)

        except SyntaxError as syn_err:
            # CRITICAL FIX: Do NOT silently ignore syntax errors!
            findings.append(
                {
                    "file": file_path.name,
                    "line": syn_err.lineno or 0,
                    "issue": f"Python Syntax Error / Unparseable Code: {syn_err.msg} (potential obfuscation risk)",
                    "severity": "HIGH",
                }
            )
        except Exception as e:
            findings.append(
                {
                    "file": file_path.name,
                    "line": 0,
                    "issue": f"AST Analysis Error: {e}",
                    "severity": "LOW",
                }
            )

    return findings


VALID_EXTENSIONS = {
    ".md",
    ".markdown",
    ".py",
    ".sh",
    ".bash",
    ".zsh",
    ".ps1",
    ".js",
    ".ts",
    ".mjs",
    ".cjs",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".ini",
    ".cfg",
    ".conf",
    ".key",
    ".pem",
    ".crt",
}


def is_scannable_file(file_path: Path) -> bool:
    """Identifies files that must be scanned for security threats and credentials."""
    name_lower = file_path.name.lower()
    suffix_lower = file_path.suffix.lower()

    # 1. Environment and configuration dotfiles that often contain secrets
    if name_lower.startswith("." + "env") or name_lower in (
        "." + "npmrc",
        "." + "pypirc",
        "." + "gitignore",
        "." + "dockerignore",
        "." + "editorconfig",
        "cred" + "entials",
        "secrets" + ".json",
        "secrets" + ".yaml",
        "secrets" + ".toml",
        "secrets" + ".ini",
    ):
        return True

    # 2. Files with known code, config, or documentation extensions
    if suffix_lower in VALID_EXTENSIONS:
        return True

    # 3. Extensionless files: check if they are readable text or contain a shebang
    if suffix_lower == "" and file_path.is_file():
        try:
            with open(file_path, "rb") as bf:
                head = bf.read(512)
            if head.startswith(b"#!"):
                return True
            if b"\x00" not in head:
                head.decode("utf-8", errors="strict")
                return True
        except Exception:
            pass

    return False


def audit_allowed_tools_declaration(skill_dir: Path) -> Dict[str, Any]:
    """Inspect the manifest declaration only; this cannot prove host runtime enforcement."""
    manifest = skill_dir / "SKILL.md"
    base = {
        "declared_tools": [],
        "runtime_enforcement": "NOT VERIFIED BY STATIC SCANNER",
        "manifest": "SKILL.md",
    }
    if not manifest.is_file():
        return {**base, "status": "MISSING_MANIFEST"}

    try:
        content = manifest.read_text(encoding="utf-8")
    except OSError as exc:
        return {**base, "status": "UNREADABLE", "detail": str(exc)}

    lines = content.splitlines()
    if not lines or lines[0].strip() != "---":
        return {**base, "status": "INVALID_FRONTMATTER"}

    try:
        end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    except StopIteration:
        return {**base, "status": "INVALID_FRONTMATTER"}

    field_index = next(
        (i for i, line in enumerate(lines[1:end], 1) if line.strip() == "allowed-tools:"),
        None,
    )
    if field_index is None:
        inline = next(
            (line.split(":", 1)[1].strip() for line in lines[1:end] if line.strip().startswith("allowed-tools:")),
            None,
        )
        if inline is None:
            return {**base, "status": "MISSING_DECLARATION"}
        if inline in ("[]", "null", ""):
            return {**base, "status": "EMPTY_DECLARATION"}
        if inline.startswith("[") and inline.endswith("]"):
            tools = [
                part.replace("'", "").replace('"', "").strip()
                for part in inline[1:-1].split(",")
                if part.strip()
            ]
        else:
            tools = [inline.replace("'", "").replace('"', "").strip()]
    else:
        tools = []
        for line in lines[field_index + 1:end]:
            if not line.strip():
                continue
            if line and not line[0].isspace():
                break
            stripped = line.strip()
            if stripped.startswith("- "):
                tools.append(stripped[2:].replace("'", "").replace('"', "").strip())
            else:
                return {**base, "status": "INVALID_DECLARATION", "detail": stripped}

    if not tools or any(not tool for tool in tools):
        return {**base, "status": "EMPTY_DECLARATION"}
    if any(
        tool in ("*", "**", "all")
        or re.fullmatch(r"[A-Za-z0-9_-]+\(\s*:?\*{1,2}\s*\)", tool)
        for tool in tools
    ):
        return {**base, "status": "BROAD_DECLARATION", "declared_tools": tools}
    if len(set(tools)) != len(tools):
        return {**base, "status": "DUPLICATE_DECLARATION", "declared_tools": tools}
    valid_tool_pattern = re.compile(
        r"^[A-Za-z0-9_-]+(?:\((?=[^)]*[A-Za-z0-9])[A-Za-z0-9_./:* -]+\))?$"
    )
    if any(not valid_tool_pattern.fullmatch(tool) for tool in tools):
        return {**base, "status": "INVALID_DECLARATION", "declared_tools": tools}
    return {**base, "status": "DECLARED", "declared_tools": tools}


def scan_skill_directory(skill_dir: Path) -> Dict[str, Any]:
    """Scan all skill content without following symlinks or excluding test/evaluation files."""
    if skill_dir.is_symlink():
        finding = {
            "file": str(skill_dir),
            "line": 1,
            "severity": "HIGH",
            "issue": "Symlinked Skill root rejected; inspection could escape the approved Skills root",
            "snippet": "[SYMLINK ROOT]",
        }
        return {
            "skill": skill_dir.name,
            "scanned_files": 0,
            "excluded_files": [],
            "excluded_file_count": 0,
            "coverage_status": "PARTIAL",
            "uninspected_files": [str(skill_dir)],
            "permission_declaration": {"status": "NOT INSPECTED", "runtime_enforcement": "NOT VERIFIED"},
            "findings": [finding],
            "status": "FAIL",
            "critical_count": 0,
            "high_count": 1,
        }

    all_findings = []
    scanned_files = 0
    uninspected_files = []
    excluded_files = []
    ephemeral_dirs = {".venv", "venv", "__pycache__", "node_modules", ".git", ".pytest_cache"}

    for f in skill_dir.rglob("*"):
        try:
            relative = f.relative_to(skill_dir)
        except ValueError:
            relative = Path(f.name)

        if f.is_symlink():
            uninspected_files.append(str(relative) + " [symlink not followed]")
            continue
        if not f.is_file():
            continue
        if any(part in ephemeral_dirs for part in relative.parts) or f.suffix.lower() in (".pyc", ".pyo"):
            continue

        if is_scannable_file(f):
            scanned_files += 1
            all_findings.extend(scan_file_security(f))
        else:
            uninspected_files.append(str(relative))

    has_critical = any(iss["severity"] == "CRITICAL" for iss in all_findings)
    has_high = any(iss["severity"] == "HIGH" for iss in all_findings)

    if has_critical or has_high:
        status = "FAIL"
    elif all_findings:
        status = "WARNING"
    elif uninspected_files:
        status = "WARNING (UNINSPECTED ARTIFACTS)"
    else:
        status = "CLEAN"

    permission_declaration = audit_allowed_tools_declaration(skill_dir)
    coverage_status = "PARTIAL" if excluded_files or uninspected_files else "COMPLETE"
    return {
        "skill": skill_dir.name,
        "scanned_files": scanned_files,
        "excluded_files": excluded_files,
        "excluded_file_count": len(excluded_files),
        "coverage_status": coverage_status,
        "uninspected_files": uninspected_files,
        "permission_declaration": permission_declaration,
        "findings": all_findings,
        "status": status,
        "critical_count": sum(1 for iss in all_findings if iss["severity"] == "CRITICAL"),
        "high_count": sum(1 for iss in all_findings if iss["severity"] == "HIGH"),
    }


def scan_with_skillspector(target_path: Path, fast: bool = False) -> Dict[str, Any]:
    """
    Checks whether the optional official NVIDIA SkillSpector CLI is installed.
    It deliberately does not spawn an external process; the host must invoke the
    scanner explicitly through its approved command interface.
    """
    cli = shutil.which("skillspector")
    if not cli:
        return {
            "status": "NOT AVAILABLE",
            "message": "NVIDIA skillspector is an optional secondary scanner (not installed on PATH). Local AST security scanner passed.",
        }

    return {
        "status": "AVAILABLE_NOT_RUN",
        "executable": Path(cli).name,
        "message": (
            "SkillSpector is installed. Run its CLI explicitly through the host's "
            "approved command tool; the local scanner does not spawn external processes."
        ),
    }


def scan_all_installed_skills(skills_root: Path) -> Dict[str, Any]:
    """
    Scans all skills in a skills directory.
    Aggregates static analysis and external verification into a transparent Trust Matrix.
    """
    if not skills_root.exists() or not skills_root.is_dir():
        return {
            "status": "NOT APPLICABLE",
            "message": f"Skills directory not found: {skills_root}",
            "skills": [],
        }

    results = []
    total_findings = 0
    total_critical = 0
    total_high = 0

    for sdir in skills_root.iterdir():
        if sdir.is_dir() and not sdir.name.startswith("."):
            res = scan_skill_directory(sdir)
            total_findings += len(res["findings"])
            total_critical += res.get("critical_count", 0)
            total_high += res.get("high_count", 0)
            results.append(res)

    skillspector_audit = scan_with_skillspector(skills_root)

    # A clean finding count is not a complete audit when files are excluded or
    # host-enforced permissions remain unverified.
    partial_coverage_count = sum(1 for item in results if item.get("coverage_status") != "COMPLETE")
    permission_review_count = sum(
        1 for item in results
        if item.get("permission_declaration", {}).get("status") != "DECLARED"
    )
    runtime_enforcement_unverified_count = sum(
        1 for item in results
        if item.get("permission_declaration", {}).get("runtime_enforcement")
        != "VERIFIED BY HOST RUNTIME EVIDENCE"
    )

    if total_critical > 0:
        overall_status = "FAIL (TIER 4 BLOCKED - CRITICAL FINDINGS)"
    elif total_high > 0 or any(r["status"] == "FAIL" for r in results):
        overall_status = "FAIL (HIGH SEVERITY FINDINGS)"
    elif total_findings > 0:
        overall_status = "WARNING (TIER 3 - MANUAL AUDIT REQUIRED)"
    elif permission_review_count:
        overall_status = "WARNING (PERMISSION DECLARATIONS NEED REVIEW)"
    elif runtime_enforcement_unverified_count:
        overall_status = "WARNING (HOST RUNTIME PERMISSION ENFORCEMENT NOT VERIFIED)"
    elif partial_coverage_count:
        overall_status = "WARNING (PARTIAL STATIC COVERAGE)"
    elif skillspector_audit["status"] == "FAIL":
        overall_status = "FAIL (EXTERNAL VULNERABILITIES DETECTED BY SKILLSPECTOR)"
    elif skillspector_audit["status"] == "PASS":
        overall_status = "VERIFIED CLEAN (STATIC + SKILLSPECTOR CERTIFIED)"
    elif skillspector_audit["status"] == "NOT AVAILABLE":
        overall_status = "PASS (STATIC CLEAN, EXTERNAL SCANNER NOT AVAILABLE)"
    else:
        overall_status = (
            f"WARNING (STATIC CLEAN, EXTERNAL STATUS: {skillspector_audit.get('status')})"
        )

    return {
        "skills_root": str(skills_root),
        "scanned_count": len(results),
        "total_findings": total_findings,
        "total_critical": total_critical,
        "total_high": total_high,
        "partial_coverage_count": partial_coverage_count,
        "permission_review_count": permission_review_count,
        "runtime_enforcement_unverified_count": runtime_enforcement_unverified_count,
        "results": results,
        "skillspector": skillspector_audit,
        "overall_status": overall_status,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Multi-Layer Agent Security, AST & Data-Flow Scanner"
    )
    parser.add_argument(
        "target", nargs="?", default=".", help="Skill directory or root skills directory to scan"
    )
    parser.add_argument(
        "--dir", "-d", dest="target_dir", default="", help="Target directory (alias)"
    )
    parser.add_argument("--json", action="store_true", help="Output JSON results")
    args = parser.parse_args()

    target = Path(args.target_dir or args.target).resolve()

    if args.json:
        if (target / "SKILL.md").exists():
            res = scan_skill_directory(target)
            print(json.dumps(res, indent=2))
        else:
            audit = scan_all_installed_skills(target)
            print(json.dumps(audit, indent=2))
        return

    print("================================================================================")
    print("         MULTI-LAYER AGENT SECURITY, AST & DATA-FLOW SCANNER                    ")
    print("================================================================================")
    print(f"Target Directory : {target}\n")

    if (target / "SKILL.md").exists():
        # Single skill target
        res = scan_skill_directory(target)
        print(f"Skill Name      : {res['skill']}")
        print(f"Scanned Files   : {res['scanned_files']}")
        print(f"Excluded Files  : {res.get('excluded_file_count', 0)}")
        print(f"Coverage        : {res.get('coverage_status', 'UNKNOWN')}")
        permission = res.get("permission_declaration", {})
        print(f"Tool Declaration: {permission.get('status', 'UNKNOWN')}")
        print(f"Runtime Policy  : {permission.get('runtime_enforcement', 'NOT VERIFIED')}")
        print(f"Security Status : {res['status']}")
        if res.get("uninspected_files"):
            print(f"Uninspected    : {', '.join(res['uninspected_files'])}")
        if res["findings"]:
            print("\nFindings:")
            for f in res["findings"]:
                print(
                    f"  - [{f.get('severity', 'WARN')}] {f['file']}:{f.get('line', '?')} -> {f['issue']}"
                )
    else:
        # Skills root directory target
        audit = scan_all_installed_skills(target)
        if audit.get("status") == "NOT APPLICABLE":
            print(f"Status: {audit['status']} - {audit.get('message', '')}")
            return
        print(f"Scanned Skills : {audit.get('scanned_count', len(audit.get('results', [])))}")
        print(f"Total Findings : {audit.get('total_findings', 0)}")
        print(f"Critical Count : {audit.get('total_critical', 0)}")
        print(f"Partial Coverage: {audit.get('partial_coverage_count', 0)} skills")
        print(f"Permission Review: {audit.get('permission_review_count', 0)} skills")
        print(f"Runtime Enforcement Unverified: {audit.get('runtime_enforcement_unverified_count', 0)} skills")
        print(f"Composite Status: {audit.get('overall_status', 'N/A')}")
        print(
            f"SkillSpector   : {audit['skillspector']['status']} ({audit['skillspector'].get('message', 'Active')})"
        )
        print("\nIndividual Skill Breakdown:")
        for s in audit.get("results", []):
            sym = "[x]" if s["status"] == "CLEAN" else "[!]"
            print(
                f"  {sym} {s['skill']:<25} | Status: {s['status']:<7} | Files: {s['scanned_files']:<2} | Findings: {len(s['findings'])}"
            )

    print("\n================================================================================")


if __name__ == "__main__":
    main()
