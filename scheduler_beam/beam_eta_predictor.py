

from scheduler.progress_callback import ProgressCallback
from utils.rolling_window import RollingWindow


class BeamEtaPredictor:

    def __init__(self, progress_callback: ProgressCallback, num_percentiles: int, num_innings: int):
        self.progress_callback = progress_callback
        self.num_innings = num_innings
        self.num_percentiles = num_percentiles
        self.total_leafs = num_percentiles ** num_innings

        self.nodes_eliminated = RollingWindow(3)

        self.leafs_searched = 0
        

    def report(self, depth):
        completed = self.num_percentiles ** (self.num_innings - depth + 1) 

        self.leafs_searched += completed
        self.nodes_eliminated.append(completed)

        per_second = self.nodes_eliminated.per_second()
        increment = completed / self.total_leafs

        percent_complete = 100 * self.leafs_searched / self.total_leafs

        msg = f"{percent_complete:.2f}% Complete.  Searching {self.total_leafs:,.0f} total schedules.  Evaluating {per_second:,.0f} per second..."
        self.progress_callback(increment, msg)