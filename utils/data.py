import numpy as np
import torch
import pickle
from collections import defaultdict


######## General Utils #############

def print_root_value(mrp, title):
    root_value_array = mrp.root_value
    print("*"*50)
    print(f"{title} = {root_value_array[0, 0].item()}")
    print(f"root value: {root_value_array}")
    print("*"*50)


def create_inclusion_case(raw_data, idx):
    assert idx < len(raw_data), "Index out of bounds for raw_data"
    test_record = raw_data[idx]
    return test_record


def create_users(x_values, y_values=None, salt_shape=1, transform_salt_shape=2, rand_bit=1, seed=None):
    #salt_shape=1
    if seed is not None:
        torch.manual_seed(seed)

    vals = torch.as_tensor(x_values, dtype=torch.float32)
    if vals.ndim == 1:
        vals = vals.unsqueeze(1)  # (n_users, 1)

    n_users, record_shape = vals.shape
    dtype = vals.dtype

    y_vals = None
    y_shape = 0
    if y_values is not None:
        y_vals = torch.as_tensor(y_values, dtype=torch.float32)
        if y_vals.ndim == 1:
            y_vals = y_vals.unsqueeze(1)  # (n_users, y_shape)
        if y_vals.shape[0] != n_users:
            raise ValueError("y_values must have the same number of users as x_values")
        y_shape = y_vals.shape[1]

    out = []
    for i in range(n_users):
        user_name = f"user_{i+1}"
        features_x = vals[i].reshape(1, record_shape)  # (1, record_shape)

        if y_vals is not None:
            features_y = y_vals[i].reshape(1, y_shape)
            features = torch.cat([features_x, features_y], dim=1)  # (1, record_shape + y_shape)
        else:
            features = features_x

        user_salt = (rand_bit * torch.randint(
            low=0, high=2**5, size=(1, salt_shape),
            dtype=torch.int64
        ).to(dtype))
        # print(user_salt)

        # if y_shape > 0:
        #     print(y_shape)
        #     pad = torch.zeros(salt_shape, y_shape, dtype=dtype)
        #     user_salt = torch.cat([user_salt, pad], dim=1)  # (salt_shape, record_shape + y_shape)

        value = torch.cat([features, user_salt], dim=1)  # ((1 + salt_shape), record_shape + y_shape)


        transform_salt = (rand_bit * torch.randint(
            low=0, high=2**15, size=(transform_salt_shape,),
            dtype=torch.int64
        ).to(dtype)).reshape(1, transform_salt_shape)

        out.append({
            "name": user_name,
            "value": value,
            "transform_salt": transform_salt
        })
    return out




########### Utils for logistic regression model ############

def prepare_coefs(path, to_tensor=True):
    with open(path, "rb") as f:
        model = pickle.load(f)
    coefs = model["coefs"]
    intercept = model["intercept"]
    if to_tensor:
        coefs = torch.tensor(coefs, dtype=torch.float32)
        intercept = torch.tensor(intercept, dtype=torch.float32)
    return coefs, intercept


def prepare_real_data(path, n_samples=None, to_tensor=True):
    with open(path, "rb") as f:
        data = pickle.load(f)
    if n_samples is None:
        n_samples = len(data["X_test"])
    X = data["X_test"][:n_samples]
    y = data["y_test"][:n_samples]
    if to_tensor:
        X = torch.tensor(X, dtype=torch.float32)
        y = torch.tensor(y, dtype=torch.float32).reshape(-1, 1)
    return X, y


def setup_logreg_HIV_example(model_path, data_path, n_samples=None, salt_shape=2, transform_salt_shape=2, rand_bit=1, seed=None):

    coefs, intercept = prepare_coefs(model_path, to_tensor=True)
    X, y = prepare_real_data(data_path, n_samples=n_samples, to_tensor=True)

    out = create_users(
        x_values=X,
        y_values=y,
        salt_shape=salt_shape,
        transform_salt_shape=transform_salt_shape,
        rand_bit=rand_bit,
        seed=seed
    )

    return out, coefs, intercept



def setup_logreg_synthetic_example(x_values, y_values, coefs, intercept, salt_shape=2, transform_salt_shape=2, rand_bit=1, seed=None):

    coefs = torch.tensor(coefs, dtype=torch.float32).reshape(1, -1)
    intercept = torch.tensor(intercept, dtype=torch.float32).reshape(1, 1)

    out = create_users(
        x_values=x_values,
        y_values=y_values,
        salt_shape=salt_shape,
        transform_salt_shape=transform_salt_shape,
        rand_bit=rand_bit,
        seed=seed
    )

    return out, coefs, intercept




########### Utils for KS test ############

def setup_ks_HD_example(data_path, n_samples=None, salt_shape=2, transform_salt_shape=2, rand_bit=1, seed=None):

    with open(data_path, "rb") as f:
        data = pickle.load(f)

    healthy_sample = data["healthy"]
    HD_sample = data["HD"]

    if n_samples is not None:
        healthy_sample = healthy_sample[:n_samples]
        HD_sample = HD_sample[:n_samples]

    print(healthy_sample)
    print(HD_sample)

    edges = torch.arange(start=10, end=90, step=5, dtype=torch.float32)

    out_s1 = create_users(
        x_values=healthy_sample,
        y_values=None,
        salt_shape=salt_shape,
        transform_salt_shape=transform_salt_shape,
        rand_bit=rand_bit,
        seed=seed
    )

    out_s2 = create_users(
        x_values=HD_sample,
        y_values=None,
        salt_shape=salt_shape,
        transform_salt_shape=transform_salt_shape,
        rand_bit=rand_bit,
        seed=seed
    )

    return out_s1, out_s2, edges




########### Utils for Linear Regression Case Study ############

class RegressionData:

    def __init__(self, file_path, add_intercept=True, n_features=None, to_tensor=True, max_tries=1000, random_state=None):
        self.file_path = file_path
        self.add_intercept = add_intercept
        self.n_features = n_features
        self.to_tensor = to_tensor
        self.max_tries = max_tries
        self.random_state = random_state
        self.load_full_data()


    def load_full_data(self):
        with open(self.file_path, 'rb') as f:
            data = pickle.load(f)

        self.full_X_train = data['X_train']
        self.full_X_test = data['X_test']
        self.full_y_train = data['y_train'].reshape(-1, 1)
        self.full_y_test = data['y_test'].reshape(-1, 1)
        self.full_feature_names = data['feature_names']

        self.N_train, self.N_test = self.full_X_train.shape[0], self.full_X_test.shape[0]
        self.F = self.full_X_train.shape[1]


    def __observation_sampling(self, X, y, n_samples=None, max_tries=1000,random_state=None):
        np.random.seed(random_state)
        N = X.shape[0]
        if n_samples is None:
            print("-- No sampling requested, using all observations.")
            return X, y
        else:
            if n_samples > self.N_train:
                raise ValueError(f"n_samples={n_samples} cannot be greater than the number of available observations={self.N_train}.")
            
            for _ in range(max_tries):
                indices = np.random.choice(N, n_samples, replace=False)
                X_temp = X[indices, :]
                y_temp = y[indices]  
                valid_x = np.all(np.std(X_temp, axis=0) > 0)  # Ensure no constant features
                valid_y = np.all(np.std(y_temp) > 0)
                if valid_x and valid_y:
                    print(f"-- Random observations selected: {indices}")
                    return X_temp, y_temp
            raise ValueError(f"Could not find a valid subset after {max_tries} tries. The requested n_samples may be too small, or the data may not allow for such variation in the subset.")
    
            


    def __feature_sampling(self, X, n_features=None):

        if self.n_features is not None:
            
            if self.n_features > self.F:
                raise ValueError(f"n_features={self.n_features} cannot be greater than the number of available features={self.F}.")
            
            groups = defaultdict(list)
            for i, col in enumerate(self.full_feature_names):
                pos = col.split('_')[0]
                groups[pos].append(i)

            pos_list = sorted(groups.keys(), key=int)
            var_groups = [groups[pos] for pos in pos_list]
            num_groups = len(var_groups)
            pointers = [0] * num_groups
            selected_indices = []

            while len(selected_indices) < n_features:
                added = False
                for g in range(num_groups):
                    if pointers[g] < len(var_groups[g]):
                        selected_indices.append(var_groups[g][pointers[g]])
                        pointers[g] += 1
                        added = True
                        if len(selected_indices) == n_features:
                            break
                if not added:
                    raise ValueError(f"Not enough features available for n_features={n_features}.")
            print("-- Selected features:", [self.full_feature_names[i] for i in selected_indices])
            self.selected_feature_indices = selected_indices
            return X[:, selected_indices]
        else:
            print("-- No feature sampling requested, using all features.")
            self.selected_feature_indices = list(range(self.F))
            return X




    def prepare_train_data(self, n_samples):

        print(f"*"*60)
        print(f"{'Preparing training data...':^60}")
        print(f"*"*60)

        X = self.full_X_train
        y = self.full_y_train
            
        X = self.__feature_sampling(X, self.n_features)
        X, y = self.__observation_sampling(X, y, n_samples, max_tries=self.max_tries, random_state=self.random_state)

        if self.add_intercept:
            X = np.hstack([np.ones((X.shape[0], 1)), X])

        if self.to_tensor:
            X = torch.tensor(X, dtype=torch.float32)
            y = torch.tensor(y, dtype=torch.float32)

        print(f"[ok] Imported training data with shape: X={X.shape}, y={y.shape}\n")
        return X, y



    def prepare_test_data(self, n_samples, strategy='first_n'):

        print(f"*"*60)
        print(f"{'Preparing test data...':^60}")
        print(f"*"*60)

        assert strategy in ['first_n', 'random'], f"Invalid strategy: {strategy}. Use 'first_n' or 'random'."

        X = self.full_X_test
        y = self.full_y_test

        if self.n_features is not None:
            if hasattr(self, 'selected_feature_indices'):
                selected_indices = self.selected_feature_indices
            else:
                raise ValueError("No feature selection has been performed. prepare training data first.")

            print(f"-- Using previously selected features: {(np.array(self.full_feature_names)[selected_indices])}")
            X = X[:, selected_indices]

        if n_samples is not None:
            if n_samples > self.N_test:
                raise ValueError(f"n_samples={n_samples} cannot be greater than the number of available observations={self.N_test}.")
            
            if strategy == "random":
                np.random.seed(self.random_state + 1)
                selected_indices = np.random.choice(np.arange(X.shape[0]), size=n_samples, replace=False)
                X = X[selected_indices]
                y = y[selected_indices]
                print(f"-- Randomly selected {n_samples} observations from test set: {selected_indices}")

            elif strategy == "first_n":
                X = X[:n_samples]
                y = y[:n_samples]
                print(f"-- Using first {n_samples} observations from test set.")
        else:
            print(f"-- Using all observations from test set.")

        if self.add_intercept:
            X = np.hstack([np.ones((X.shape[0], 1)), X])

        if self.to_tensor:
            X = torch.tensor(X, dtype=torch.float32)
            y = torch.tensor(y, dtype=torch.float32)

        print(f"[ok] Imported test data with shape: X={X.shape}, y={y.shape}\n")
        return X, y