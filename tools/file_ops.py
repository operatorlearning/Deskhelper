# -*- coding: utf-8 -*-
"""
文件操作工具
支持：文件读写、复制、移动、删除、搜索、压缩
"""

import os
import shutil
import glob
from pathlib import Path
from typing import List, Optional
from datetime import datetime

from loguru import logger


class FileOps:
    """文件系统操作工具"""

    def read_text(self, path: str, encoding: str = "utf-8") -> str:
        """读取文本文件"""
        try:
            with open(path, "r", encoding=encoding) as f:
                content = f.read()
            logger.debug(f"读取文件: {path} ({len(content)} chars)")
            return content
        except Exception as e:
            logger.error(f"读取文件失败 {path}: {e}")
            raise

    def write_text(self, path: str, content: str, encoding: str = "utf-8") -> bool:
        """写入文本文件（自动创建父目录）"""
        try:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w", encoding=encoding) as f:
                f.write(content)
            logger.info(f"写入文件: {path}")
            return True
        except Exception as e:
            logger.error(f"写入文件失败 {path}: {e}")
            return False

    def append_text(self, path: str, content: str, encoding: str = "utf-8") -> bool:
        """追加写入文本文件"""
        try:
            with open(path, "a", encoding=encoding) as f:
                f.write(content)
            return True
        except Exception as e:
            logger.error(f"追加写入失败 {path}: {e}")
            return False

    def copy_file(self, src: str, dst: str) -> bool:
        """复制文件"""
        try:
            Path(dst).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            logger.info(f"复制文件: {src} -> {dst}")
            return True
        except Exception as e:
            logger.error(f"复制文件失败: {e}")
            return False

    def move_file(self, src: str, dst: str) -> bool:
        """移动/重命名文件"""
        try:
            Path(dst).parent.mkdir(parents=True, exist_ok=True)
            shutil.move(src, dst)
            logger.info(f"移动文件: {src} -> {dst}")
            return True
        except Exception as e:
            logger.error(f"移动文件失败: {e}")
            return False

    def delete_file(self, path: str) -> bool:
        """删除文件"""
        try:
            p = Path(path)
            if p.is_file():
                p.unlink()
            elif p.is_dir():
                shutil.rmtree(path)
            logger.info(f"删除: {path}")
            return True
        except Exception as e:
            logger.error(f"删除失败 {path}: {e}")
            return False

    def list_dir(
        self,
        path: str,
        pattern: str = "*",
        recursive: bool = False,
    ) -> List[str]:
        """列出目录内容"""
        try:
            p = Path(path)
            if recursive:
                files = list(p.rglob(pattern))
            else:
                files = list(p.glob(pattern))
            result = [str(f) for f in files]
            logger.debug(f"列出目录 {path}: {len(result)} 个文件")
            return result
        except Exception as e:
            logger.error(f"列出目录失败 {path}: {e}")
            return []

    def search_files(
        self,
        directory: str,
        name_pattern: str,
        content_keyword: Optional[str] = None,
    ) -> List[str]:
        """搜索文件"""
        matches = []
        for f in Path(directory).rglob(name_pattern):
            if f.is_file():
                if content_keyword is None:
                    matches.append(str(f))
                else:
                    try:
                        text = f.read_text(encoding="utf-8", errors="ignore")
                        if content_keyword in text:
                            matches.append(str(f))
                    except Exception:
                        pass
        logger.info(f"搜索 '{name_pattern}' 找到 {len(matches)} 个文件")
        return matches

    def get_file_info(self, path: str) -> dict:
        """获取文件信息"""
        p = Path(path)
        if not p.exists():
            return {"error": "文件不存在"}
        stat = p.stat()
        return {
            "name": p.name,
            "path": str(p.absolute()),
            "size": stat.st_size,
            "size_human": self._human_size(stat.st_size),
            "modified": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
            "is_dir": p.is_dir(),
            "suffix": p.suffix,
        }

    def create_dir(self, path: str) -> bool:
        """创建目录（含所有父目录）"""
        try:
            Path(path).mkdir(parents=True, exist_ok=True)
            logger.info(f"创建目录: {path}")
            return True
        except Exception as e:
            logger.error(f"创建目录失败: {e}")
            return False

    def zip_files(self, files: List[str], output_path: str) -> bool:
        """压缩文件"""
        import zipfile
        try:
            with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for f in files:
                    zf.write(f, Path(f).name)
            logger.info(f"压缩完成: {output_path}")
            return True
        except Exception as e:
            logger.error(f"压缩失败: {e}")
            return False

    def _human_size(self, size: int) -> str:
        """格式化文件大小"""
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} PB"

