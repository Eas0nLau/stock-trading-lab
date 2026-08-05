import os
import shutil
import subprocess
from loguru import logger

def run():
    # 1. 定位 front 文件夹
    current_dir = os.getcwd()
    front_dir = os.path.join(current_dir, 'front')

    if not os.path.exists(front_dir):
        logger.info(f"❌ 错误：当前目录下不存在 'front' 文件夹！\n当前路径：{current_dir}")
        exit(1)

    logger.info(f"✅ 准备进入目录：{front_dir}")

    # 2. 启动 npm run dev（使用 Popen + cwd 参数）
    try:
        if os.name == 'nt':
            npm_path = shutil.which('npm.cmd')
            if not npm_path:
                npm_path = os.path.join(os.environ.get('ProgramFiles', r'C:\Program Files'), 'nodejs', 'npm.cmd')
            node_dir = os.path.dirname(npm_path)
            node_path = os.path.join(node_dir, 'node.exe')
            npm_cli_path = os.path.join(node_dir, 'node_modules', 'npm', 'bin', 'npm-cli.js')
            if not os.path.isfile(node_path) or not os.path.isfile(npm_cli_path):
                raise FileNotFoundError(npm_path)
            npm_command = [node_path, npm_cli_path, 'run', 'dev']
            process_env = os.environ.copy()
            process_env['PATH'] = node_dir + os.pathsep + process_env.get('PATH', '')
            creation_flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
        else:
            npm_command = ['npm', 'run', 'dev']
            process_env = None
            creation_flags = 0
        process = subprocess.Popen(
            npm_command,
            cwd=front_dir,  # 直接指定工作目录，无需 os.chdir
            env=process_env,
            shell=False,
            creationflags=creation_flags,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            encoding='utf-8',
            errors='replace'
        )

        logger.info(f"🚀 npm run dev 已成功启动！")
        logger.info(f"   进程 PID: {process.pid}")
        logger.info("   （开发服务器正在后台运行，按 Ctrl+C 可停止）")

        # 可选：实时打印 npm 的输出（开发时推荐开启）
        for line in process.stdout:
            logger.info(str(line).strip(), end='')

    except FileNotFoundError:
        logger.info("❌ 错误：系统中未找到 npm 命令！")
        logger.info("   请确认已安装 Node.js，并且 npm 已添加到系统 PATH 中。")
    except Exception as e:
        logger.info(f"❌ 执行失败：{e}")
