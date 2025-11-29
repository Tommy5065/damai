import logging
import sys

# 获取日志收集器
logger = logging.getLogger(name="damai")
# 设置日志登记
logger.setLevel(logging.DEBUG)

# 调用模块时,如果频繁多次错误,每次会添加handler,造成重复日志,每次都移除所有的handler,后面再重新添加
while logger.hasHandlers():
    for i in logger.handlers:
        logger.removeHandler(i)

# 对日志文件格式设置
formatter = logging.Formatter(
    "%(asctime)s-%(pathname)s[line:%(lineno)d]-%(levelname)s: %(message)s"
)
fh = logging.FileHandler(r"test_logger.log", encoding="utf-8")  # 日志文件路径，格式名称
fh.setLevel(logging.DEBUG)  # 日志打印级别
fh.setFormatter(fmt=formatter)
logger.addHandler(fh)

# 控制台输出控制
ch = logging.StreamHandler(sys.stdout)
ch.setLevel(logging.DEBUG)
ch.setFormatter(fmt=formatter)
logger.addHandler(ch)
