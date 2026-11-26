class PoolEmptyException(Exception):
    def __str__(self):
        """
        proxyproof is used out
        :return:
        """
        return repr('no proxy in proxyproof')
