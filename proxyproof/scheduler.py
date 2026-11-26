import multiprocessing
import os
import signal
import time

from loguru import logger

from proxyproof.processors.getter import Getter
from proxyproof.processors.server import app
from proxyproof.processors.tester import Tester
from proxyproof.setting import (
    API_HOST,
    API_PORT,
    API_THREADED,
    APP_PROD_METHOD,
    APP_PROD_METHOD_GEVENT,
    APP_PROD_METHOD_MEINHELD,
    APP_PROD_METHOD_TORNADO,
    CYCLE_GETTER,
    CYCLE_TESTER,
    ENABLE_GETTER,
    ENABLE_SERVER,
    ENABLE_TESTER,
    IS_PROD,
    IS_WINDOWS,
)

if IS_WINDOWS:
    multiprocessing.freeze_support()

tester_process, getter_process, server_process = None, None, None


class Scheduler:
    """
    scheduler
    """

    def run_tester(self, cycle=CYCLE_TESTER):
        """
        run tester
        """
        if not IS_WINDOWS:
            # fork 的子进程继承了父进程注册的 SIGTERM handler（指向父进程的对象空间，
            # 在这里跑会抛 AttributeError）。子进程要的是默认动作：收到信号直接退出。
            signal.signal(signal.SIGTERM, signal.SIG_DFL)
            signal.signal(signal.SIGINT, signal.SIG_DFL)
        if not ENABLE_TESTER:
            logger.info('tester not enabled, exit')
            return
        tester = Tester()
        loop = 0
        while True:
            logger.debug(f'tester loop {loop} start...')
            t0 = time.time()
            tester.run()
            loop += 1
            # tester.run() 已经用掉了 cycle 秒的预算，这里只补差额。
            # 直接 sleep(cycle) 会让检测器一半时间在空转，吞吐砍半。
            time.sleep(max(0.5, cycle - (time.time() - t0)))

    def run_getter(self, cycle=CYCLE_GETTER):
        """
        run getter
        """
        if not IS_WINDOWS:
            # 同 run_tester：子进程要默认信号动作，不继承父进程的 handler
            signal.signal(signal.SIGTERM, signal.SIG_DFL)
            signal.signal(signal.SIGINT, signal.SIG_DFL)
        if not ENABLE_GETTER:
            logger.info('getter not enabled, exit')
            return
        getter = Getter()
        loop = 0
        while True:
            logger.debug(f'getter loop {loop} start...')
            getter.run()
            loop += 1
            time.sleep(cycle)

    def run_server(self):
        """
        run server for api
        """
        if not IS_WINDOWS:
            # 同 run_tester：子进程要默认信号动作，不继承父进程的 handler
            signal.signal(signal.SIGTERM, signal.SIG_DFL)
            signal.signal(signal.SIGINT, signal.SIG_DFL)
        if not ENABLE_SERVER:
            logger.info('server not enabled, exit')
            return
        if IS_PROD:
            # 缺依赖就明确报错退出。以前是 except ImportError 只打一条日志就 return，
            # server 进程无声结束，调用方只看到端口连不上，要翻日志才知道是没装包。
            if APP_PROD_METHOD == APP_PROD_METHOD_GEVENT:
                try:
                    from gevent.pywsgi import WSGIServer
                except ImportError as e:
                    raise RuntimeError('APP_PROD_METHOD=gevent，请先 pip install gevent') from e
                WSGIServer((API_HOST, API_PORT), app).serve_forever()

            elif APP_PROD_METHOD == APP_PROD_METHOD_TORNADO:
                try:
                    from tornado.httpserver import HTTPServer
                    from tornado.ioloop import IOLoop
                    from tornado.wsgi import WSGIContainer
                except ImportError as e:
                    raise RuntimeError('APP_PROD_METHOD=tornado，请先 pip install tornado') from e
                HTTPServer(WSGIContainer(app)).listen(API_PORT)
                IOLoop.instance().start()

            elif APP_PROD_METHOD == APP_PROD_METHOD_MEINHELD:
                try:
                    import meinheld
                except ImportError as e:
                    raise RuntimeError('APP_PROD_METHOD=meinheld，请先 pip install meinheld') from e
                meinheld.listen((API_HOST, API_PORT))
                meinheld.run(app)

            else:
                # setting.py 在导入时已经校验过，这里只是防御
                raise ValueError(f'unsupported APP_PROD_METHOD={APP_PROD_METHOD!r}')
        else:
            app.run(host=API_HOST, port=API_PORT, threaded=API_THREADED, use_reloader=False)

    def run(self):
        global tester_process, getter_process, server_process

        if not IS_WINDOWS:
            # 容器/服务器的正确退出路径：docker stop 发 SIGTERM，
            # 默认行为是立即死亡、子进程变孤儿继续抓取。这里转发给子进程再收尾。
            def _shutdown(signum, frame):
                logger.info(f'received {signal.Signals(signum).name}, stopping children...')
                for p in (tester_process, getter_process, server_process):
                    if p and p.pid and p.is_alive():
                        # 用 os.kill 直接发信号而不是 p.terminate()：
                        # fork 的子进程会继承这个 handler，p.terminate() 触发子进程里
                        # 自己的 handler，而子进程里那些 Process 对象从未 start()，
                        # _popen 是 None，抛 AttributeError。os.kill 不存在这个问题，
                        # 且子进程入口处已把 SIGTERM 重置为默认动作。
                        os.kill(p.pid, signum)
            signal.signal(signal.SIGTERM, _shutdown)
            signal.signal(signal.SIGINT, _shutdown)

        try:
            logger.info('starting proxyproof...')
            if ENABLE_TESTER:
                tester_process = multiprocessing.Process(
                    target=self.run_tester)
                logger.info(f'starting tester, pid {tester_process.pid}...')
                tester_process.start()

            if ENABLE_GETTER:
                getter_process = multiprocessing.Process(
                    target=self.run_getter)
                logger.info(f'starting getter, pid {getter_process.pid}...')
                getter_process.start()

            if ENABLE_SERVER:
                server_process = multiprocessing.Process(
                    target=self.run_server)
                logger.info(f'starting server, pid {server_process.pid}...')
                server_process.start()

            tester_process and tester_process.join()
            getter_process and getter_process.join()
            server_process and server_process.join()
        except KeyboardInterrupt:
            logger.info('received keyboard interrupt signal')
            tester_process and tester_process.terminate()
            getter_process and getter_process.terminate()
            server_process and server_process.terminate()
        finally:
            # must call join method before calling is_alive
            tester_process and tester_process.join()
            getter_process and getter_process.join()
            server_process and server_process.join()
            if tester_process:
                logger.info(
                    f'tester is {"alive" if tester_process.is_alive() else "dead"}')
            if getter_process:
                logger.info(
                    f'getter is {"alive" if getter_process.is_alive() else "dead"}')
            if server_process:
                logger.info(
                    f'server is {"alive" if server_process.is_alive() else "dead"}')
            logger.info('proxy terminated')


if __name__ == '__main__':
    scheduler = Scheduler()
    scheduler.run()
