import supervisor.xmlrpc
import xmlrpclib


class Supervisor(object):

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

    def start_process(self, name):
        result = self._supervisor.startProcess(name)
        return result

    def restart_process(self, name):
        result = self._supervisor.stopProcess(name, wait=True)
        if not result:
            # Restarting failed, as process did not stop
            return False

        result = self._supervisor.startProcess(name)
        return result

    def stop_process(self, name):
        result = self._supervisor.stopProcess(name, wait=True)
        return result


# s = Supervisor()
# s.connect(
#     'http://127.0.0.1',
#     'unix:///home/lars/lib/supervisor/tmp/supervisor.sock')
