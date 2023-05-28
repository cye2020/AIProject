import numpy as np
from os import PathLike
from typing import List, Tuple, Union
from pathlib import Path
from .config import TRACK2INST, DRUMDISTRIBUTION
from sklearn.metrics import ConfusionMatrixDisplay, PrecisionRecallDisplay, RocCurveDisplay, DetCurveDisplay
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
from sklearn.metrics.pairwise import cosine_similarity
from scipy.spatial.distance import jensenshannon
from scipy.stats import wasserstein_distance
import matplotlib.pyplot as plt

ArrayLike = Union[np.ndarray[float], List[float]]

def calculate_score(y_true: ArrayLike, y_pred: ArrayLike) -> Tuple[float, float, float, float]:
    accuracy = accuracy_score(y_true, y_pred)
    precision = precision_score(y_true, y_pred, zero_division=1)
    recall = recall_score(y_true, y_pred, zero_division=1)
    f1 = f1_score(y_true, y_pred, zero_division=1)
    return accuracy, precision, recall, f1

def calculate_distribution_similarity(dist1: ArrayLike, dist2: ArrayLike) -> Tuple[float, float, float]:
    # Jensen-Shannon Divergence (JSD)
    jsd_score = jensenshannon(dist1, dist2)
    # Earth Mover's Distance (EMD)
    emd_score = wasserstein_distance(dist1, dist2)
    # Cosine Similarity
    cosine_score = cosine_similarity([dist1], [dist2])[0][0]
    return jsd_score, emd_score, cosine_score


def plot_confusion_matrix(y_true, y_pred, save_dir: PathLike=None, save=False, show=False):
    ConfusionMatrixDisplay.from_predictions(y_true, y_pred, cmap='Blues')
    if save: plt.savefig(save_dir / 'Confusion_Matrix.png')
    if show: plt.show()

def plot_precision_recall(y_true, y_pred, save_dir: PathLike=None, save=False, show=False):
    PrecisionRecallDisplay.from_predictions(y_true, y_pred)
    plt.legend().remove()
    if save: plt.savefig(save_dir / 'Precision_Recall.png')
    if show: plt.show()

def plot_roc_curve(y_true, y_pred, save_dir: PathLike=None, save=False, show=False):
    RocCurveDisplay.from_predictions(y_true, y_pred)
    plt.legend().remove()
    if save: plt.savefig(save_dir / 'Roc_Curve.png')
    if show: plt.show()

def plot_det_curve(y_true, y_pred, save_dir: PathLike=None, save=False, show=False):
    DetCurveDisplay.from_predictions(y_true, y_pred)
    plt.legend().remove()
    if save: plt.savefig(save_dir / 'Det_Curve.png')
    if show: plt.show()

def plot_distribution(count, save_dir: PathLike=None, save=False, show=False):
    x = np.arange(1, len(count)+1)
    plt.bar(x, count)
    plt.xlabel('Timestep')
    plt.ylabel('Probability')
    plt.xticks(x)
    plt.legend().remove()
    if save: plt.savefig(save_dir / 'Distribution.png')
    if show: plt.show()


class TestTaker:
    def __init__(self, inst_class: np.ndarray, output: np.ndarray, name=None) -> None:
        self.inst_class = inst_class.T  # shape (5, timestep) -> (timestep, 5)
        output = output.transpose(2, 0, 1)  # shape (17, 128, timestep) -> (timestep, 17, 128)
        self.output: np.ndarray = np.any(output != 0, axis=2)  # shape (timesteps, tracks)
        self.name = name
        self.timesteps = self.inst_class.shape[0]
        self.score: List[Tuple] = None
    
    def set_score(self, im_score, ir_score, dp_score):
        self.score = [im_score, ir_score, dp_score]
    
    def print_score(self):
        print(f'[{self.name} IM Test Score]')
        print(f'Accuracy: {self.score[0][0]}, Precision: {self.score[0][1]}, Recall: {self.score[0][2]}, F1 Score: {self.score[0][3]}')
        print(f'\n[{self.name} IR Test Score]')
        print(f'Accuracy: {self.score[1][0]}, Precision: {self.score[1][1]}, Recall: {self.score[1][2]}, F1 Score: {self.score[1][3]}')
        print(f'\n[{self.name} DP Test Score]')
        print(f"Jensen-Shannon Divergence: {self.score[2][0]}, Earth Mover's Distance: {self.score[2][1]}, Cosine Similarity: {self.score[2][2]}")


class Evaluator:
    def __init__(self, root: PathLike) -> None:
        self.root = Path(root)
        
        # Result Plot Directory
        self.im_dir = Path(root) / 'IMTest'
        self.ir_dir = Path(root) / 'IRTest'
        self.dp_dir = Path(root) / 'DPTest'
        for test_path in [self.im_dir, self.ir_dir, self.dp_dir]:
            test_path.mkdir(parents=True, exist_ok=True)

        # Result
        self.im_true, self.im_pred, self.ir_true, self.ir_pred = [], [], [], []
        self.dp_pred = np.zeros(12)

    def calculate_total_score(self) -> Tuple[float, float, float]:
        im_score = calculate_score(self.im_true, self.im_pred)
        ir_score = calculate_score(self.ir_true, self.ir_pred)
        total_sum = np.sum(self.dp_pred)
        dp_dist = self.dp_pred / total_sum
        dp_score = calculate_distribution_similarity(DRUMDISTRIBUTION, dp_dist)
        return im_score, ir_score, dp_score
    
    def plot_total(self, save=False, show=False) -> None:
        self.plot_IMTest(save, show)
        self.plot_IRTest(save, show)
        self.plot_DPTest(save, show)
    
    def __call__(self, taker: TestTaker) -> Tuple[Tuple, Tuple, Tuple]:
        im_score = self.IMTest(taker)
        ir_score = self.IRTest(taker)
        dp_score = self.DPTest(taker)
        taker.set_score(im_score, ir_score, dp_score)
    
    
    def IMTest(self, taker: TestTaker) -> Tuple[float, float, float, float]:
        '''
        Input Match Test
        '''
        y_true = []
        y_pred = []
        for timestep in range(taker.timesteps):
            insts = taker.inst_class[timestep]
            pred_insts = np.zeros(5)
            tracks = taker.output[timestep]
            for idx, track in enumerate(tracks):
                inst = TRACK2INST[idx]
                ori = pred_insts[inst]
                pred_insts[inst] = max(ori, int(track))
            y_true.extend(insts)
            y_pred.extend(pred_insts)
        self.im_true.extend(y_true), self.im_pred.extend(y_pred)
        im_score = calculate_score(y_true, y_pred)
        return im_score
                
    
    def IRTest(self, taker: TestTaker) -> Tuple[float, float, float, float]:
        '''
        Input Response Test
        '''
        y_true = []
        y_pred = []
        for timestep in range(taker.timesteps):
            insts = taker.inst_class[timestep]
            tracks = taker.output[timestep]
            label = np.any(insts)
            predict = np.any(tracks)
            y_true.append(label)
            y_pred.append(predict)

        self.ir_true.extend(y_true), self.ir_pred.extend(y_pred)
        ir_score = calculate_score(y_true, y_pred)
        return ir_score
            
    
    def DPTest(self, taker: TestTaker) -> Tuple[float, float, float]:
        '''
        Drum Pattern Test
        '''
        drums: np.ndarray = taker.output.T[0]
        if not drums.any():
            return None
        dp_pred = np.zeros(12)
        num_iterations = taker.timesteps // 12
        for iter in range(num_iterations):
            beat = drums[iter * 12:(iter + 1) * 12]
            true_indices = np.where(beat)[0]
            dp_pred[true_indices] += 1
        
        self.dp_pred += dp_pred
        total_sum = np.sum(dp_pred)
        dp_dist = dp_pred / total_sum
        dp_score = calculate_distribution_similarity(DRUMDISTRIBUTION, dp_dist)
        return dp_score
    
    def plot_IMTest(self, save=False, show=False) -> None:
        plot_confusion_matrix(self.im_true, self.im_pred, self.im_dir, save, show)
        plot_precision_recall(self.im_true, self.im_pred, self.im_dir, save, show)
        plot_roc_curve(self.im_true, self.im_pred, self.im_dir, save, show)
        plot_det_curve(self.im_true, self.im_pred, self.im_dir, save, show)
    
    def plot_IRTest(self, save=False, show=False) -> None:
        plot_confusion_matrix(self.ir_true, self.ir_pred, self.ir_dir, save, show)
        plot_precision_recall(self.ir_true, self.ir_pred, self.ir_dir, save, show)
        plot_roc_curve(self.ir_true, self.ir_pred, self.ir_dir, save, show)
        plot_det_curve(self.ir_true, self.ir_pred, self.ir_dir, save, show)
    
    def plot_DPTest(self, save, show) -> None:
        total_sum = np.sum(self.dp_pred)
        dp_dist = self.dp_pred / total_sum
        plot_distribution(dp_dist, self.dp_dir, save, show)