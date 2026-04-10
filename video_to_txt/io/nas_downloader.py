"""NAS 文件访问模块，支持 SFTP 协议."""
from __future__ import annotations

import os
import stat
from dataclasses import dataclass
from pathlib import PurePosixPath

import paramiko

VIDEO_EXTENSIONS = {'.mp4', '.mov', '.avi', '.mkv', '.flv', '.wmv', '.webm', '.m4v', '.ts', '.rmvb'}


@dataclass
class NasConfig:
    """NAS 连接配置，从环境变量读取."""

    host: str
    user: str
    password: str
    port: int = 22

    @classmethod
    def from_env(cls) -> NasConfig:
        """从环境变量构建 NAS 配置.

        Returns:
            NasConfig 实例.

        Raises:
            ValueError: 必要环境变量未配置时抛出.
        """
        host = os.environ.get('NAS_HOST', '')
        user = os.environ.get('NAS_USER', '')
        password = os.environ.get('NAS_PASS', '')
        port = int(os.environ.get('NAS_PORT', '22'))
        if not host or not user:
            raise ValueError('NAS 配置缺失，请设置 NAS_HOST / NAS_USER / NAS_PASS 环境变量')
        return cls(host=host, user=user, password=password, port=port)


def _open_sftp(config: NasConfig) -> tuple:
    """建立 SSH 连接并返回 (SSHClient, SFTPClient).

    Args:
        config: NAS 连接配置.

    Returns:
        (ssh, sftp) 元组.
    """
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(config.host, port=config.port, username=config.user, password=config.password, timeout=30)
    return ssh, ssh.open_sftp()


def is_video_file(path: str) -> bool:
    """判断路径是否为视频文件（按扩展名）.

    Args:
        path: 文件路径或文件名.

    Returns:
        True 如果是视频文件.
    """
    return PurePosixPath(path).suffix.lower() in VIDEO_EXTENSIONS


def list_video_files(config: NasConfig, nas_path: str, exclude: list[str] | None = None) -> list[str]:
    """递归列出 NAS 目录下的所有视频文件.

    Args:
        config: NAS 连接配置.
        nas_path: NAS 上的目录路径.
        exclude: 需要排除的子路径列表.

    Returns:
        视频文件的完整路径列表.
    """
    exclude_set = set(exclude or [])
    results: list[str] = []
    ssh, sftp = _open_sftp(config)
    try:
        _walk_sftp(sftp, nas_path, exclude_set, results)
    finally:
        sftp.close()
        ssh.close()
    return results


def _walk_sftp(sftp, path: str, exclude: set[str], results: list[str]) -> None:
    """递归遍历 SFTP 目录，收集视频文件路径.

    Args:
        sftp: SFTPClient 实例.
        path: 当前遍历路径.
        exclude: 需要跳过的路径集合.
        results: 收集结果的列表（原地修改）.
    """
    if path in exclude:
        return
    try:
        entries = sftp.listdir_attr(path)
    except Exception:
        return
    for entry in entries:
        full_path = f'{path.rstrip("/")}/{entry.filename}'
        if stat.S_ISDIR(entry.st_mode):
            _walk_sftp(sftp, full_path, exclude, results)
        elif is_video_file(entry.filename):
            results.append(full_path)


def download_file(config: NasConfig, remote_path: str, local_path: str) -> None:
    """从 NAS 下载单个文件到本地.

    Args:
        config: NAS 连接配置.
        remote_path: NAS 上的文件路径.
        local_path: 本地保存路径.
    """
    ssh, sftp = _open_sftp(config)
    try:
        sftp.get(remote_path, local_path)
    finally:
        sftp.close()
        ssh.close()
