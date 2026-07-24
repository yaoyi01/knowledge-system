#!/usr/bin/env python3
"""
知识库 Pipeline 主入口
用法: python3 pipeline.py <文件路径>
      python3 pipeline.py --watch <监控目录>  # 未来 Phase 3
"""
import sys
import time
import sqlite3
from pathlib import Path

BASE_DIR = Path.home() / "Documents" / "knowledge-system"

# 确保 cleaner 可导入
sys.path.insert(0, str(BASE_DIR))

from cleaner.state import init_db, DB_PATH, update_status, stats
from cleaner.format_check import check_file
from cleaner.dedup import process as dedup_process, quarantine
from cleaner.metadata import extract as extract_metadata


def process_file(file_path: str, conn=None) -> dict:
    """
    对单个文件执行完整清理流程
    返回处理结果
    """
    close_conn = False
    if conn is None:
        conn = sqlite3.connect(str(DB_PATH))
        close_conn = True

    try:
        # ── Stage 1: 格式检查 ──
        t0 = time.time()
        result = check_file(file_path)
        if not result["valid"]:
            q = quarantine(file_path, result["reason"])
            print(f"  ❌ 格式检查失败: {result['reason']} → {q}")
            if close_conn:
                conn.close()
            return {"status": "rejected", "reason": result["reason"]}

        print(f"  ✓ 格式检查通过: {result['file_type']} ({result['file_size']} bytes)")

        # ── Stage 2: 去重 ──
        dedup_result = dedup_process(
            conn,
            file_path=file_path,
            file_type=result["file_type"],
            file_size=result["file_size"],
            mime_type=result.get("mime_type"),
        )
        if dedup_result["is_duplicate"]:
            print(f"  ⏭ 已跳过 (重复文件)")
            if close_conn:
                conn.close()
            return {"status": "skipped", "reason": "duplicate"}

        file_hash = dedup_result["file_hash"]
        print(f"  ✓ 归档: {dedup_result['vault_path']}")

        # ── Stage 3: 元数据提取 ──
        meta = extract_metadata(
            file_path=file_path,
            file_type=result["file_type"],
            file_hash=file_hash,
            conn=conn,
        )
        print(f"  ✓ 元数据: { {k: v for k, v in meta.items() if v} }")

        # ── Stage 4: 文本提取 ──
        from processors import process
        proc_result = process(file_hash, result["file_type"], dedup_result["vault_path"], conn)
        if proc_result and proc_result.get("text_path"):
            print(f"  ✓ 文本提取: {proc_result['text_path']}")
            update_status(conn, file_hash, "text_done")

            # ── Stage 5: RAG 索引 ──
            from rag_index import index_text
            text = Path(proc_result["text_path"]).read_text(encoding="utf-8")
            chunk_ids = index_text(file_hash, text, proc_result.get("meta", {}), conn)
            print(f"  ✓ RAG: {len(chunk_ids)} chunks → Qdrant")
            update_status(conn, file_hash, "rag_done")

            # ── Stage 6: Wiki 预备 ──
            from wiki_ingest import stage_for_wiki
            stage_for_wiki(file_hash, proc_result["text_path"], conn)
            update_status(conn, file_hash, "wiki_ready")
        else:
            update_status(conn, file_hash, "text_done")

        duration = (time.time() - t0) * 1000
        print(f"  ✅ 完成 ({duration:.0f}ms)")

        if close_conn:
            conn.close()

        return {
            "status": "processed",
            "file_hash": file_hash,
            "file_type": result["file_type"],
            "vault_path": dedup_result["vault_path"],
            "meta": meta,
        }

    except Exception as e:
        print(f"  💥 处理异常: {e}")
        if close_conn:
            conn.close()
        return {"status": "error", "reason": str(e)}


def main():
    init_db()
    conn = sqlite3.connect(str(DB_PATH))

    if len(sys.argv) < 2:
        s = stats(conn)
        print("📊 当前状态:")
        for status, count in sorted(s.items()):
            print(f"  {status}: {count}")
        print()
        print("用法: python3 pipeline.py <文件路径>")
        print("      python3 pipeline.py --scan     # 扫描配置的目录，处理新文件")
        print("      python3 pipeline.py --watch    # 实时监听文件变化")
        print("      python3 pipeline.py --process  # 处理所有已清理的文件")
        conn.close()
        return

    # 监听模式: 实时监控配置目录中的新文件
    if sys.argv[1] == "--watch":
        import yaml
        from watchdog.observers import Observer
        from watchdog.events import FileSystemEventHandler

        config_path = BASE_DIR / "config.yaml"
        config = yaml.safe_load(config_path.read_text()) if config_path.exists() else {}
        watch_dirs = [Path(p).expanduser() for p in config.get("watch_dirs", ["~/Documents", "~/Downloads", "~/Desktop"])]
        exclude_dirs = set(config.get("exclude", {}).get("dirs", []))
        include_types_str = config.get("include_types", [])
        include_exts = set()
        for group in include_types_str:
            for ext in group.split(","):
                ext = ext.strip()
                if not ext.startswith("."):
                    ext = f".{ext}"
                include_exts.add(ext)

        class Handler(FileSystemEventHandler):
            def on_created(self, event):
                if event.is_directory:
                    return
                path = Path(event.src_path)
                if path.suffix.lower() not in include_exts:
                    return
                parts = set(path.parent.parts)
                if parts & exclude_dirs:
                    return
                print(f"\n📥 {path.name}")
                process_file(str(path), conn)
                conn.commit()

        observer = Observer()
        for wd in watch_dirs:
            if wd.exists():
                observer.schedule(Handler(), str(wd), recursive=True)
                print(f"👁 监听: {wd}")
        observer.start()
        print("按 Ctrl+C 停止\n")
        try:
            while True:
                import time
                time.sleep(1)
        except KeyboardInterrupt:
            observer.stop()
            observer.join()
        conn.close()
        return
    if sys.argv[1] == "--scan":
        import yaml
        config_path = BASE_DIR / "config.yaml"
        if not config_path.exists():
            print("❌ config.yaml 不存在，请先配置 watch_dirs")
            conn.close()
            return
        config = yaml.safe_load(config_path.read_text())
        watch_dirs = [Path(p).expanduser() for p in config.get("watch_dirs", [])]
        exclude_dirs = set(config.get("exclude", {}).get("dirs", []))
        include_types_str = config.get("include_types", [])
        # 展平类型列表
        include_exts = set()
        for group in include_types_str:
            for ext in group.split(","):
                ext = ext.strip()
                if not ext.startswith("."):
                    ext = f".{ext}"
                include_exts.add(ext)

        print(f"🔍 扫描 {len(watch_dirs)} 个目录...")
        all_files = []
        for wd in watch_dirs:
            if not wd.exists():
                continue
            for f in wd.rglob("*"):
                if not f.is_file():
                    continue
                if f.suffix.lower() not in include_exts:
                    continue
                parts = set(f.relative_to(wd).parts)
                if parts & exclude_dirs:
                    continue
                all_files.append(f)

        print(f"  找到 {len(all_files)} 个文件\n")
        for i, f in enumerate(all_files, 1):
            print(f"[{i}/{len(all_files)}] {f.name}")
            process_file(str(f), conn)
            conn.commit()
            print()
        print(f"✅ 扫描完成")
        conn.close()
        return
    if sys.argv[1] == "--dir":
        if len(sys.argv) < 3:
            print("用法: pipeline.py --dir <目录路径>")
            conn.close(); return
        target = Path(sys.argv[2]).expanduser()
        if not target.exists():
            print(f"❌ 目录不存在: {target}"); conn.close(); return
        exts = {".docx",".doc",".xlsx",".xls",".pptx",".ppt",".pdf",
                ".jpg",".jpeg",".png",".gif",".webp",".bmp",
                ".mp4",".mov",".avi",".mkv",".mp3",".wav",".m4a",".aac",
                ".xmind",".mm",".opml",".vsdx",
                ".md",".txt",".csv",".json",".yaml",
                ".py",".js",".ts",".jsx",".tsx",".go",".rs",".java",".c",".cpp",".h"}
        files = [f for f in target.rglob("*") if f.is_file() and f.suffix.lower() in exts]
        total = len(files)
        print(f"📂 {target}")
        print(f"   预扫描: {total} 个文件")
        if total == 0: conn.close(); return
        print(f"   [0/{total}] 开始处理...")
        for i, f in enumerate(files, 1):
            pct = i * 100 // total
            bar = "█" * (pct // 5) + "░" * (20 - pct // 5)
            print(f"   [{pct:3d}%] {bar}  {i}/{total}  {f.name}")
            process_file(str(f), conn)
            conn.commit()
        print(f"✅ 完成: {total} 个文件")
        conn.close()
        return
    if sys.argv[1] == "--resume":
        print("🔍 查找中断的文件...")
        pending = conn.execute(
            "SELECT original_path, file_hash FROM files WHERE status IN ('validated','processing','text_done')"
        ).fetchall()
        if not pending:
            print("   没有中断的文件"); conn.close(); return
        total = len(pending)
        print(f"   找到 {total} 个中断文件，继续处理...")
        for i, (path, fhash) in enumerate(pending, 1):
            pct = i * 100 // total if total else 0
            bar = "█" * (pct // 5) + "░" * (20 - pct // 5)
            print(f"   [{pct:3d}%] {bar}  {i}/{total}")
            p = Path(path)
            if p.exists():
                process_file(str(p), conn)
            else:
                print(f"     ⚠️ 文件不存在: {path}")
                conn.execute("UPDATE files SET status='error' WHERE file_hash=?", (fhash,))
            conn.commit()
        print(f"✅ 续扫完成")
        conn.close()
        return
    if sys.argv[1] == "--process":
        rows = conn.execute(
            "SELECT file_hash, file_type, vault_path, original_name FROM files WHERE status IN ('processing','validated','processed')",
        ).fetchall()
        if not rows:
            print("没有待处理的文件")
            conn.close()
            return
        print(f"📦 处理 {len(rows)} 个文件\n")
        for i, (file_hash, file_type, vault, name) in enumerate(rows, 1):
            Path(vault)  # validate
            if file_type in ("docx","xlsx","pptx","pdf","text","code"):
                from processors import process
                proc_result = process(file_hash, file_type, vault, conn)
                if proc_result and proc_result.get("text_path"):
                    text = Path(proc_result["text_path"]).read_text(encoding="utf-8")
                    print(f"  [{i}/{len(rows)}] {name}: {len(text)} chars", end="")
                    from rag_index import index_text
                    ids = index_text(file_hash, text, proc_result.get("meta",{}), conn)
                    print(f" → {len(ids)} chunks", end="")
                    from wiki_ingest import stage_for_wiki
                    stage_for_wiki(file_hash, proc_result["text_path"], conn)
                    conn.execute("UPDATE files SET status='indexed' WHERE file_hash=?", (file_hash,))
                    conn.commit()
            print()
        print(f"✅ 完成")
        conn.close()
        return

    target = sys.argv[1]
    path = Path(target)

    if not path.exists():
        print(f"❌ 文件不存在: {target}")
        conn.close()
        return

    if path.is_file():
        result = process_file(str(path), conn)
        conn.commit()
    elif path.is_dir():
        print(f"📂 批量处理: {target}")
        files = [f for f in path.rglob("*") if f.is_file()]
        print(f"  共 {len(files)} 个文件\n")
        for i, f in enumerate(files, 1):
            print(f"[{i}/{len(files)}] {f.name}")
            process_file(str(f), conn)
            conn.commit()
            print()
        print(f"✅ 批量完成")

    conn.close()


if __name__ == "__main__":
    main()
