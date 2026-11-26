import multiprocessing
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
