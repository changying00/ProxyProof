import importlib
import inspect
import pkgutil

from .base import BaseCrawler

# load classes subclass of BaseCrawler
classes = []
for _, name, is_pkg in pkgutil.walk_packages(__path__, prefix=f'{__name__}.'):
    if is_pkg:
        continue
    module = importlib.import_module(name)
    for name, value in inspect.getmembers(module):
        globals()[name] = value
        # 只接受"定义在自己模块里的类"。子类模块会 `from ..base_list import TextListCrawler`，
        # 若不按 __module__ 过滤，同一个基类会被每个子类模块重复注册一次。
        if inspect.isclass(value) and issubclass(value, BaseCrawler) and value is not BaseCrawler \
                and value.__module__ == module.__name__ \
                and not getattr(value, 'ignore', False):
            classes.append(value)
__all__ = __ALL__ = classes

