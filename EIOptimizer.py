import numpy as np
from scipy.stats import norm
from scipy.optimize import minimize
from sklearn.preprocessing import StandardScaler
import GPy

class EIOptimizer():
    
    def __init__(self):
        pass
    
    def fit(self, X, y, bounds = None, num_restarts = 10):
        self.opt_value = np.min(y)
        self.input_dimension = X.shape[1]
        if bounds is not None:
            self.min_bounds = np.array([x[0] for x in bounds])
            self.max_bounds = np.array([x[1] for x in bounds])
            assert (np.min(X, axis = 0) >= self.min_bounds).all()
            assert (np.max(X, axis = 0) <= self.max_bounds).all()
        else:
            self.min_bounds = np.min(X, axis = 0)
            self.max_bounds = np.max(X, axis = 0)
        self.X_normalized = (X - self.min_bounds) / (self.max_bounds - self.min_bounds) 
        self.y_scaler = StandardScaler()
        self.y_normalized = self.y_scaler.fit_transform(y.reshape(-1, 1))
        kernel = GPy.kern.RBF(input_dim=self.input_dimension, variance=0.1, lengthscale=0.1,
                             ARD=True)
        kernel.lengthscale.constrain_bounded(0.001, 10.0) 
        kernel.variance.constrain_bounded(0.001, 100.0) 
        self.gp_model = GPy.models.GPRegression(self.X_normalized, self.y_normalized, kernel)
        self.gp_model.Gaussian_noise.constrain_bounded(1e-4, 10.0)
        self.gp_model.optimize_restarts(messages=False, optimizer='lbfgsb', 
                                        num_restarts=num_restarts, max_iters=500, verbose = False)
        
        
    def wrap(self, point, margin = 0.1):
        result = []
        for i in range(self.input_dimension):
            result.append((np.max([0, point[i] - margin]), 
                           np.min([1, point[i] + margin])))
        return result
    
    def minus_log_expected_improvement(self, point):
        mean_values, variance_values = self.gp_model.predict(point.reshape(1, -1))
        estimated_values = mean_values.ravel()
        eps = 0.05/len(estimated_values)
        delta = self.opt_value - estimated_values - eps
        estimated_errors = (variance_values ** 0.5).ravel()
        non_zero_error_inds = np.where(estimated_errors > 1e-6)[0]
        Z = np.zeros(len(delta))
        Z[non_zero_error_inds] = delta[non_zero_error_inds]/estimated_errors[non_zero_error_inds]
        log_EI = np.log(estimated_errors) + norm.logpdf(Z) + np.log(1 + Z * np.exp(norm.logcdf(Z) - norm.logpdf(Z)))
        return -log_EI
        
    
    def sample(self, n_samples = 1, population_factor = 1.0):
        assert population_factor >= 1.0
        population_size = int(population_factor* n_samples) 
        initial_guess = np.random.rand(population_size, self.input_dimension)
        polished_points = []
        polished_values = []
        for i in range(len(initial_guess)):
            result = minimize(self.minus_log_expected_improvement, initial_guess[i], method='L-BFGS-B',
                              options={'disp': False}, bounds=self.wrap(initial_guess[i]))
            polished_points.append(result.x)
            polished_values.append(result.fun[0])
        top_inds = np.argsort(np.array(polished_values))[:n_samples]
        return self.min_bounds + (self.max_bounds - self.min_bounds) * np.array(polished_points)[top_inds]
