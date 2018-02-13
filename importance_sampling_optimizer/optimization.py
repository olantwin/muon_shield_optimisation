from sklearn.ensemble import GradientBoostingRegressor
from skopt import Optimizer
from skopt.learning import GaussianProcessRegressor
from skopt.learning import RandomForestRegressor
from skopt.learning import GradientBoostingQuantileRegressor


class RandomSearchOptimizer:
    def __init__(self, space, random_state=None):
        self.space_ = space
        self.state_ = random_state

    def tell(self, X, y):
        pass

    def ask(self, n_points=1, strategy=None):
        return self.space_.rvs(n_points, random_state=self.state_)


def CreateOptimizer(clf_type, space, random_state=None):
    if clf_type == 'rf':
        clf = Optimizer(
            space,
            RandomForestRegressor(n_estimators=500, max_depth=7, n_jobs=-1),
            random_state=random_state
        )
    elif clf_type == 'gb':
        clf = Optimizer(
            space,
            GradientBoostingQuantileRegressor(
                base_estimator=GradientBoostingRegressor(
                    n_estimators=100,
                    max_depth=4,
                    loss='quantile'
                )
            ),
            random_state=random_state
        )
    elif clf_type == 'gp':
        clf = Optimizer(
            space,
            GaussianProcessRegressor(
                alpha=1e-7,
                normalize_y=True,
                noise='gaussian'
            ),
            random_state=random_state
        )
    else:
        clf = RandomSearchOptimizer(space, random_state=random_state)

    return clf
