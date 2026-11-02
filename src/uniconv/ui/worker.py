"""Runs JobRunner.run() off the UI thread; a long video would otherwise freeze the window."""

from PySide6.QtCore import QObject, QThread, Signal, Slot

from uniconv.core.converter import CancelToken
from uniconv.core.jobs import Job, JobRunner


class JobWorker(QObject):
    progress = Signal(float)   # 0.0..1.0 for the current item
    finished = Signal(list)    # list[ItemResult]

    def __init__(self, runner: JobRunner, job: Job) -> None:
        super().__init__()
        self._runner, self._job = runner, job
        self.cancel_token = CancelToken()

    @Slot()
    def run(self) -> None:
        results = self._runner.run(self._job, self.cancel_token,
                                   on_progress=lambda _i, p: self.progress.emit(p))
        self.finished.emit(results)


def start_job(runner: JobRunner, job: Job, parent: QObject) -> tuple[QThread, JobWorker]:
    thread = QThread(parent)
    worker = JobWorker(runner, job)
    worker.moveToThread(thread)
    thread.started.connect(worker.run)
    worker.finished.connect(thread.quit)
    worker.finished.connect(worker.deleteLater)
    thread.finished.connect(thread.deleteLater)
    thread.start()
    return thread, worker  # caller keeps references until finished
