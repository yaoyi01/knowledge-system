#!/usr/bin/env python3
"""
PageIndex — 代码文件 AST 级索引
用法:
  导入: python3 pageindex.py import ~/projects/my-project
  搜索: python3 pageindex.py search "函数名" [--lang py] [--type function|class|import]
"""

import sqlite3
import json
import re
import os
import sys
from pathlib import Path
from datetime import datetime

# ─── 配置 ───────────────────────────────────────────
BASE_DIR = Path.home() / "Documents" / "knowledge-system" / "pageindex"
DB_PATH = BASE_DIR / "index.db"
FILES_DIR = BASE_DIR / "files"

# ─── 语言识别 ────────────────────────────────────────
LANG_MAP = {
    ".py": "python",
    ".pyw": "python",
    ".js": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".jsx": "javascript",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".c": "c",
    ".h": "c",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".cxx": "cpp",
    ".hpp": "cpp",
    ".rb": "ruby",
    ".swift": "swift",
    ".kt": "kotlin",
    ".sh": "shell",
    ".bash": "shell",
}

IGNORE_DIRS = {
    "node_modules", ".git", "__pycache__", ".venv", "venv",
    "dist", "build", ".next", "target", ".idea", ".vscode",
    "vendor", "bower_components",
}

# ─── 正则解析器 ──────────────────────────────────────

def parse_python(lines):
    """解析 Python: def, class, import, from"""
    funcs, classes, imports = [], [], []
    in_class = None

    for i, raw in enumerate(lines, 1):
        line = raw.rstrip()
        stripped = line.lstrip()

        # 跳过注释行
        if stripped.startswith("#"):
            continue

        indent = len(line) - len(stripped)

        # 函数定义
        m = re.match(r'(async\s+)?def\s+(\w+)\s*\(([^)]*)\)', stripped)
        if m:
            name = m.group(2)
            params = m.group(3).strip() if m.group(3) else ""
            async_prefix = "async " if m.group(1) else ""
            visibility = "private" if name.startswith("_") else "public"
            funcs.append({
                "name": name,
                "signature": f"{async_prefix}def {name}({params})",
                "line": i,
                "visibility": visibility,
                "class_name": in_class,
            })

        # 类定义
        m = re.match(r'class\s+(\w+)\s*(?:\(([^)]*)\))?\s*:', stripped)
        if m:
            name = m.group(1)
            parent = m.group(2).strip() if m.group(2) else None
            classes.append({"name": name, "line": i, "parent": parent})
            in_class = name

        # import
        m = re.match(r'import\s+(.+?)(?:\s+#|$)', stripped)
        if m:
            modules = [x.strip().split(" as ")[0].strip() for x in m.group(1).split(",")]
            for mod in modules:
                imports.append({"module": mod, "symbols": None, "line": i})

        m = re.match(r'from\s+(\S+)\s+import\s+(.+?)(?:\s+#|$)', stripped)
        if m:
            module = m.group(1)
            imports.append({"module": module, "symbols": m.group(2).strip(), "line": i})

    return funcs, classes, imports


def parse_javascript(lines):
    """解析 JS/TS: function, class, const/let/var, import"""
    funcs, classes, imports = [], [], []

    for i, line in enumerate(lines, 1):
        s = line.strip()
        if s.startswith("//") or s.startswith("*"):
            continue

        # 函数: function name() / name = function() / name = () =>
        m = re.match(r'(?:async\s+)?function\s+(\w+)\s*\(', s)
        if m:
            funcs.append({"name": m.group(1), "signature": s[:80], "line": i, "visibility": "public"})

        m = re.match(r'(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s*)?\(', s)
        if m:
            funcs.append({"name": m.group(1), "signature": s[:80], "line": i, "visibility": "public"})

        m = re.match(r'(\w+)\s*=\s*(?:async\s+)?function', s)
        if m:
            funcs.append({"name": m.group(1), "signature": s[:80], "line": i, "visibility": "public"})

        # 箭头函数赋值
        m = re.match(r'(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s*)?\([^)]*\)\s*=>', s)
        if m:
            funcs.append({"name": m.group(1), "signature": s[:80], "line": i, "visibility": "public"})

        # 类
        m = re.match(r'class\s+(\w+)', s)
        if m:
            classes.append({"name": m.group(1), "line": i, "parent": None})

        # import/require
        m = re.match(r"import\s+.*\s+from\s+['\"]([^'\"]+)", s)
        if m:
            imports.append({"module": m.group(1), "symbols": None, "line": i})
        m = re.match(r"import\s+['\"]([^'\"]+)", s)
        if m:
            imports.append({"module": m.group(1), "symbols": None, "line": i})
        m = re.match(r"const\s+\w+\s*=\s*require\(['\"]([^'\"]+)", s)
        if m:
            imports.append({"module": m.group(1), "symbols": None, "line": i})

    return funcs, classes, imports


def parse_go(lines):
    """解析 Go: func, type, import"""
    funcs, classes, imports = [], [], []
    in_import = False

    for i, line in enumerate(lines, 1):
        s = line.strip()

        # import block
        if re.match(r'import\s*\(', s):
            in_import = True
            continue
        if in_import and s == ")":
            in_import = False
            continue
        if in_import:
            m = re.match(r'"([^"]+)"', s)
            if m:
                imports.append({"module": m.group(1), "symbols": None, "line": i})
            continue

        m = re.match(r'import\s+"([^"]+)"', s)
        if m:
            imports.append({"module": m.group(1), "symbols": None, "line": i})

        m = re.match(r'func\s+(?:\([^)]+\)\s+)?(\w+)\s*\(', s)
        if m:
            name = m.group(1)
            visibility = "public" if name[0].isupper() else "private"
            funcs.append({"name": name, "signature": s[:80], "line": i, "visibility": visibility})

        m = re.match(r'type\s+(\w+)\s+struct', s)
        if m:
            classes.append({"name": m.group(1), "line": i, "parent": None})

    return funcs, classes, imports


def parse_rust(lines):
    """解析 Rust: fn, struct, impl, use, mod"""
    funcs, classes, imports = [], [], []

    for i, line in enumerate(lines, 1):
        s = line.strip()

        m = re.match(r'(?:pub\s+)?(?:async\s+)?fn\s+(\w+)\s*[<(]', s)
        if m:
            name = m.group(1)
            visibility = "public" if "pub" in s else "private"
            funcs.append({"name": name, "signature": s[:80], "line": i, "visibility": visibility})

        m = re.match(r'(?:pub\s+)?struct\s+(\w+)', s)
        if m:
            classes.append({"name": m.group(1), "line": i, "parent": None})

        m = re.match(r'use\s+(.+?);', s)
        if m:
            imports.append({"module": m.group(1).strip(), "symbols": None, "line": i})

    return funcs, classes, imports


def parse_java(lines):
    """解析 Java: class, method, import"""
    funcs, classes, imports = [], [], []

    for i, line in enumerate(lines, 1):
        s = line.strip()

        m = re.match(r'import\s+([\w.]+(?:\.[*\w]+)?)\s*;', s)
        if m:
            imports.append({"module": m.group(1), "symbols": None, "line": i})

        m = re.match(r'(?:public|private|protected)?\s*(?:static|final|abstract)?\s*class\s+(\w+)', s)
        if m:
            classes.append({"name": m.group(1), "line": i, "parent": None})

        m = re.match(r'(?:public|private|protected)?\s*(?:static|final)?\s*(?:\w+(?:<[^>]+>)?\s+)?(\w+)\s*\(', s)
        if m and not s.endswith(";"):
            funcs.append({"name": m.group(1), "signature": s[:80], "line": i, "visibility": "public"})

    return funcs, classes, imports


def parse_clike(lines):
    """解析 C/C++: function definitions"""
    funcs, classes, imports = [], [], []

    for i, line in enumerate(lines, 1):
        s = line.strip()
        m = re.match(r'#include\s+[<"]([^>"]+)[>"]', s)
        if m:
            imports.append({"module": m.group(1), "symbols": None, "line": i})

        m = re.match(r'(?:static\s+)?(?:inline\s+)?(?:\w+(?:\s*\*)?\s+)+(\w+)\s*\(', s)
        if m and not s.endswith(";") and not s.startswith("//"):
            name = m.group(1)
            if name not in ("if", "while", "for", "switch", "return"):
                funcs.append({"name": name, "signature": s[:80], "line": i, "visibility": "public"})

    return funcs, classes, imports


PARSERS = {
    "python": parse_python,
    "javascript": parse_javascript,
    "typescript": parse_javascript,
    "go": parse_go,
    "rust": parse_rust,
    "java": parse_java,
    "c": parse_clike,
    "cpp": parse_clike,
}

# ─── 数据库 ─────────────────────────────────────────

def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_path TEXT UNIQUE NOT NULL,
            language TEXT NOT NULL,
            file_size INTEGER,
            line_count INTEGER,
            functions_count INTEGER DEFAULT 0,
            classes_count INTEGER DEFAULT 0,
            indexed_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS functions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_id INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            signature TEXT,
            start_line INTEGER,
            visibility TEXT,
            class_name TEXT
        );

        CREATE TABLE IF NOT EXISTS classes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_id INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            start_line INTEGER,
            parent_class TEXT
        );

        CREATE TABLE IF NOT EXISTS imports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_id INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
            module TEXT NOT NULL,
            symbols TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_func_name ON functions(name);
        CREATE INDEX IF NOT EXISTS idx_class_name ON classes(name);
        CREATE INDEX IF NOT EXISTS idx_import_module ON imports(module);
        CREATE INDEX IF NOT EXISTS idx_files_path ON files(file_path);
        CREATE INDEX IF NOT EXISTS idx_files_lang ON files(language);

        -- FTS5 全文索引 (文件路径)
        CREATE VIRTUAL TABLE IF NOT EXISTS files_fts USING fts5(
            file_path, content='files', content_rowid='id'
        );
    """)
    conn.commit()
    return conn


def import_file(conn, file_path, language):
    """导入单个文件"""
    path = Path(file_path)
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
    except Exception:
        return None

    lines = content.split("\n")
    parser = PARSERS.get(language)
    if not parser:
        return None

    funcs, classes, imports = parser(lines)

    # 写入 files 表
    cur = conn.execute(
        "INSERT OR REPLACE INTO files (file_path, language, file_size, line_count, functions_count, classes_count) VALUES (?, ?, ?, ?, ?, ?)",
        (str(path.resolve()), language, os.path.getsize(path), len(lines), len(funcs), len(classes)),
    )
    file_id = cur.lastrowid

    # 删除旧索引
    conn.execute("DELETE FROM functions WHERE file_id = ?", (file_id,))
    conn.execute("DELETE FROM classes WHERE file_id = ?", (file_id,))
    conn.execute("DELETE FROM imports WHERE file_id = ?", (file_id,))

    # 写入函数
    conn.executemany(
        "INSERT INTO functions (file_id, name, signature, start_line, visibility, class_name) VALUES (?, ?, ?, ?, ?, ?)",
        [(file_id, f["name"], f["signature"], f["line"], f.get("visibility", "public"), f.get("class_name")) for f in funcs],
    )

    # 写入类
    conn.executemany(
        "INSERT INTO classes (file_id, name, start_line, parent_class) VALUES (?, ?, ?, ?)",
        [(file_id, c["name"], c["line"], c.get("parent")) for c in classes],
    )

    # 写入 imports
    conn.executemany(
        "INSERT INTO imports (file_id, module, symbols) VALUES (?, ?, ?)",
        [(file_id, imp["module"], imp.get("symbols")) for imp in imports],
    )

    return {"path": str(path), "lang": language, "funcs": len(funcs), "classes": len(classes), "imports": len(imports)}


def import_directory(conn, root_path):
    """递归导入目录"""
    root = Path(root_path).resolve()
    stats = {"files": 0, "funcs": 0, "classes": 0, "skipped": 0}

    for path in root.rglob("*"):
        if not path.is_file():
            continue

        # 跳过忽略目录
        parts = set(path.relative_to(root).parts)
        if parts & IGNORE_DIRS:
            continue

        ext = path.suffix.lower()
        language = LANG_MAP.get(ext)
        if not language:
            continue

        result = import_file(conn, str(path), language)
        if result:
            stats["files"] += 1
            stats["funcs"] += result["funcs"]
            stats["classes"] += result["classes"]
            print(f"  {result['lang']:12s} {result['funcs']:3d}f {result['classes']:2d}c  {result['path']}")
        else:
            stats["skipped"] += 1

    conn.commit()
    return stats


def clear_index(conn):
    """清空索引"""
    conn.execute("DELETE FROM functions")
    conn.execute("DELETE FROM classes")
    conn.execute("DELETE FROM imports")
    conn.execute("DELETE FROM files")
    conn.execute("DELETE FROM files_fts")
    conn.commit()


def search(conn, query, lang=None, stype=None):
    """搜索代码符号"""
    results = []

    if stype in (None, "function"):
        sql = """
            SELECT f.name, f.signature, f.start_line, f.visibility, fl.file_path, fl.language
            FROM functions f JOIN files fl ON f.file_id = fl.id
            WHERE f.name LIKE ?
        """
        params = [f"%{query}%"]
        if lang:
            sql += " AND fl.language = ?"
            params.append(lang)
        sql += " ORDER BY f.name LIMIT 50"
        for row in conn.execute(sql, params):
            results.append({"type": "function", "name": row[0], "detail": row[1], "line": row[2], "visibility": row[3], "file": row[4], "lang": row[5]})

    if stype in (None, "class"):
        sql = """
            SELECT c.name, c.parent_class, c.start_line, fl.file_path, fl.language
            FROM classes c JOIN files fl ON c.file_id = fl.id
            WHERE c.name LIKE ?
        """
        params = [f"%{query}%"]
        if lang:
            sql += " AND fl.language = ?"
            params.append(lang)
        sql += " ORDER BY c.name LIMIT 50"
        for row in conn.execute(sql, params):
            results.append({"type": "class", "name": row[0], "detail": f"extends {row[1]}" if row[1] else "", "line": row[2], "file": row[3], "lang": row[4]})

    if stype in (None, "import"):
        sql = """
            SELECT i.module, i.symbols, fl.file_path, fl.language
            FROM imports i JOIN files fl ON i.file_id = fl.id
            WHERE i.module LIKE ?
        """
        params = [f"%{query}%"]
        if lang:
            sql += " AND fl.language = ?"
            params.append(lang)
        sql += " ORDER BY i.module LIMIT 50"
        for row in conn.execute(sql, params):
            results.append({"type": "import", "name": row[0], "detail": row[1] or "", "file": row[2], "lang": row[3]})

    return results


def stats(conn):
    """索引统计"""
    files = conn.execute("SELECT COUNT(*) FROM files").fetchone()[0]
    funcs = conn.execute("SELECT COUNT(*) FROM functions").fetchone()[0]
    classes = conn.execute("SELECT COUNT(*) FROM classes").fetchone()[0]
    imports = conn.execute("SELECT COUNT(*) FROM imports").fetchone()[0]
    langs = conn.execute("SELECT language, COUNT(*) FROM files GROUP BY language ORDER BY COUNT(*) DESC").fetchall()
    return {"files": files, "funcs": funcs, "classes": classes, "imports": imports, "langs": langs}


# ─── CLI ────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return

    conn = init_db()
    cmd = sys.argv[1]

    if cmd == "import":
        if len(sys.argv) < 3:
            print("用法: pageindex.py import <目录路径>")
            return
        root = sys.argv[2]
        print(f"📦 导入: {root}")
        st = import_directory(conn, root)
        print(f"\n✅ 完成: {st['files']} 文件, {st['funcs']} 函数, {st['classes']} 类, {st['skipped']} 跳过")

    elif cmd == "search":
        if len(sys.argv) < 3:
            print("用法: pageindex.py search <查询> [--lang py] [--type function|class|import]")
            return
        query = sys.argv[2]
        lang = None
        stype = None
        if "--lang" in sys.argv:
            idx = sys.argv.index("--lang")
            lang = sys.argv[idx + 1]
        if "--type" in sys.argv:
            idx = sys.argv.index("--type")
            stype = sys.argv[idx + 1]

        results = search(conn, query, lang, stype)
        if not results:
            print(f"🔍 '{query}' — 无结果")
        else:
            print(f"🔍 '{query}' — {len(results)} 条结果")
            print("=" * 70)
            for r in results:
                loc = f":{r['line']}" if r.get("line") else ""
                print(f"  [{r['type']:8s}] {r['name']}")
                if r.get("detail"):
                    print(f"             {r['detail']}")
                print(f"             {r['file']}{loc}  ({r['lang']})")
                print()

    elif cmd == "stats":
        s = stats(conn)
        print(f"📊 PageIndex 统计")
        print(f"  文件: {s['files']}  函数: {s['funcs']}  类: {s['classes']}  import: {s['imports']}")
        print(f"  语言:")
        for lang, count in s["langs"]:
            print(f"    {lang:12s} {count} 文件")

    elif cmd == "clear":
        clear_index(conn)
        print("🗑️ 索引已清空")

    else:
        print(f"未知命令: {cmd}")
        print("可用: import <dir> | search <query> | stats | clear")

    conn.close()


if __name__ == "__main__":
    main()
