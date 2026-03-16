from PyQt5.QtCore import QObject, QThread, pyqtSignal


class TaskWorker(QObject):

    progress = pyqtSignal(str)
    finished = pyqtSignal(object)
    error = pyqtSignal(str)

    def __init__(self, task_func, *args, **kwargs):
        super().__init__()
        self.task_func = task_func
        self.args = args
        self.kwargs = kwargs
            
    def run(self):
        try:
            result = self.task_func(self.progress.emit, *self.args, **self.kwargs)
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))
            self.finished.emit(None)


class TaskRunner:

    def __init__(self, parent=None):
        self.parent = parent
        self.thread = None
        self.worker = None

    def start(self, task_func, *args, on_progress=None, on_finished=None, on_error=None, **kwargs):

        self.thread = QThread(self.parent)
        self.worker = TaskWorker(task_func, *args, **kwargs)

        self.worker.moveToThread(self.thread)

        self.thread.started.connect(self.worker.run)

        if on_progress:
            self.worker.progress.connect(on_progress)

        if on_finished:
            self.worker.finished.connect(on_finished)

        if on_error:
            self.worker.error.connect(on_error)

        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)

        self.thread.start()