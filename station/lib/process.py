import logging
import xmlrpclib
import supervisor.xmlrpc

logger = logging.getLogger('eventstreamr')


class SupervisorProxy(object):
    """
    Proxy to communicate with Supervisor via XMLRPC

    s = SupervisorProxy()
    s.connect(
        'http://127.0.0.1',
        'unix:///home/user/lib/supervisor/tmp/supervisor.sock')
    """

    def __init__(self):
        self.proxy = None
        self._supervisor = None

    def connect(self, url, sock):
        transport = supervisor.xmlrpc.SupervisorTransport(None, None, sock)
        p = xmlrpclib.ServerProxy(url, transport=transport)
        self.proxy = p
        self._supervisor = p.supervisor

    def supervisor_state(self):
        return self._supervisor.getState()

    def process_state(self, name):
        return self._supervisor.getProcessInfo(name)

    def start_process(self, name, wait=True):
        return self._supervisor.startProcess(name, wait)

    def restart_process(self, name):
        result = self.stop_process(name, True)
        if not result:
            # Restarting failed, as process did not stop
            return False

        return self.start_process(name)

    def stop_process(self, name, wait=True):
        return self._supervisor.stopProcess(name, wait)

    def reread(self):
        try:
            result = self._supervisor.reloadConfig()
        except xmlrpclib.Fault, e:
            if e.faultCode == supervisor.xmlrpc.Faults.SHUTDOWN_STATE:
                logger.error('ERROR: supervisor shutting down')
            elif e.faultCode == supervisor.xmlrpc.Faults.CANT_REREAD:
                logger.error('ERROR: %s' % e.faultString)
            else:
                raise
        return result
