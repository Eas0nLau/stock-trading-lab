import os
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
        process = subprocess.Popen(
            ['npm', 'run', 'dev'],
            cwd=front_dir,  # 直接指定工作目录，无需 os.chdir
            shell=True,  # Windows 下强烈建议开启，否则 npm 可能报错
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            encoding='utf-8'
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