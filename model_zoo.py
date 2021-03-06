import numpy as np
import torch
import torch.nn as nn
import torch.nn.init as init
import torch.nn.functional as F
from torch.autograd import Variable
import data_utils


class Model(nn.Module):
    """Base object for a model
        Parameters
        ----------
        args: namespace object
    """

    def __init__(self, args):
        super(Model, self).__init__()
        # self.history_len = args.history_len
        self.num_states = args.num_states
        self.num_actions = args.num_actions
        self.grid_shape = (args.grid_shape, args.grid_shape)
        self.use_cuda = data_utils.use_cuda

    def print_model(self):
        print("<--------Model-------->")

    def _init_weights(self):
        """Weight initialization to be override
            Parameters
            ----------
            Returns
            -------
        """
        pass

    def _reset(self):
        """Must call in every model __init__() function
            Parameters
            ----------
            Returns
            -------
        """
        self._init_weights()
        self.print_model()


class LinearApprox(Model):
    """Basic linear approximation method of Q-learning
        Parameters
        ----------
        args: namespace object
    """

    def __init__(self, args):
        super(LinearApprox, self).__init__(args)
        self.hidden_dim = args.hidden_dim
        self.eps_start = args.eps_start
        self.eps_end = args.eps_end
        self.eps_decay = args.eps_decay
        self.output = nn.Linear(self.num_states, self.num_actions, bias=False)
        self._steps = 0

        self._reset()

    def _init_weights(self):
        pass

    def forward(self, state):
        state_vec = Variable(self._encode_state(state)).type(data_utils.FloatTensor)
        return self.output(state_vec)

    def _encode_state(self, state):
        """Create One-hot Vector of Current State
            Parameters
            ----------
            state: input state
            Returns
            -------
            One-hot torch FloatTensor: (1, num_states)
        """
        return torch.eye(self.num_states)[state - 1].view(1, self.num_states)

    def select_action(self, Q_vec):
        sample = np.random.random()
        eps_threshold = self.eps_end + (self.eps_start - self.eps_end) * \
            np.exp(-1. * self._steps / self.eps_decay)
        self._steps += 1
        if sample > eps_threshold:
            if self.use_cuda:
                return int(Q_vec.data.cpu().max(1)[1].numpy())
            else:
                return int(Q_vec.data.max(1)[1].numpy())
        else:
            return int(np.random.choice(self.num_actions))


class DQN_approx(Model):
    def __init__(self, args):
        super(DQN_approx, self).__init__(args)
        self.eps_start = args.eps_start
        self.eps_end = args.eps_end
        self.eps_decay = args.eps_decay
        self.hidden_dim = args.hidden_dim
        self.fc1 = nn.Linear(2, self.num_actions, bias=False)
        self.output = nn.Linear(self.num_actions, self.num_actions, bias=False)
        self.relu = nn.ReLU()
        self._steps = 0

        self._reset()

    def _init_weights(self):
        pass

    def forward(self, state, flag):
        x = Variable(torch.from_numpy(self._encode_state(state)),
                     volatile=flag).type(data_utils.Tensor)
        x = self.fc1(x)
        return self.output(x)
        # return x

    def _encode_state(self, state):
        """Create One-hot Vector of Current State
            Parameters
            ----------
            state: input state
            Returns
            -------
            One-hot torch FloatTensor: (1, num_states)
        """
        return np.array(np.unravel_index(state, self.grid_shape)).reshape(-1, 2)

    def select_action(self, Q_vec):
        sample = np.random.random()
        eps_threshold = self.eps_end + (self.eps_start - self.eps_end) * \
            np.exp(-1. * self._steps / self.eps_decay)
        self._steps += 1
        if sample > eps_threshold:
            if self.use_cuda:
                return int(Q_vec.data.cpu().max(1)[1].numpy())
            else:
                return int(Q_vec.data.max(1)[1].numpy())
        else:
            return int(np.random.choice(self.num_actions))


class DQN_tabular(Model):
    def __init__(self, args):
        super(DQN_tabular, self).__init__(args)
        self.conv1 = nn.Conv2d(1, 4, kernel_size=3, stride=1)
        self.conv2 = nn.Conv2d(4, 4, kernel_size=3, stride=1)
        self.output = nn.Linear((self.grid_shape[0] - 4) ** 2 * 4, 9)
        self.eps_start = args.eps_start
        self.eps_end = args.eps_end
        self.eps_decay = args.eps_decay
        self._steps = 0

        self._reset()

    def _init_weights(self):
        pass

    def forward(self, state, flag):
        x = Variable(torch.from_numpy(self._encode_state(state)),
                     volatile=flag).type(data_utils.Tensor)
        if self.use_cuda:
            x.cuda()
        x = self.conv1(x)
        x = self.conv2(x)
        Q_vec = self.output(x.view(x.size(0), -1))
        return Q_vec

    def _encode_state(self, state):
        encoded_state = np.zeros(
            (state.shape[0], 1, self.grid_shape[0], self.grid_shape[1]), dtype=int)
        state_index = np.unravel_index(state, self.grid_shape)
        if np.asarray(state_index[0]) != ():
            encoded_state[np.arange(len(state_index[0])),
                          0, state_index[0], state_index[1]] = 1.
        else:
            encoded_state[np.arange(1), 0, state_index[0], state_index[1]] = 1.
        return encoded_state

    def select_action(self, Q_vec):
        sample = np.random.random()
        eps_threshold = self.eps_end + (self.eps_start - self.eps_end) * \
            np.exp(-1. * self._steps / self.eps_decay)
        self._steps += 1
        if sample > eps_threshold:
            if self.use_cuda:
                return int(Q_vec.data.cpu().max(1)[1].numpy())
            else:
                return int(Q_vec.data.max(1)[1].numpy())
        else:
            return int(np.random.choice(self.num_actions))


class MA_hunter(Model):
    def __init__(self, args, num_hunters):
        super(MA_hunter, self).__init__(args)
        self.num_hunters = num_hunters
        self.eps_start = args.eps_start
        self.eps_end = args.eps_end
        self.eps_decay = args.eps_decay
        self.hidden_dim = args.hidden_dim
        self.fc1 = nn.Linear(2 * self.num_hunters, self.hidden_dim * self.num_hunters, bias=False)
        self.output = nn.Linear(self.hidden_dim * self.num_hunters, self.num_actions * self.num_hunters, bias=False)
        self.relu = nn.ReLU()
        self._steps = 0

        self._reset()

    def _init_weights(self):
        pass

    def forward(self, state, flag):
        n = state.shape[0]
        x = Variable(torch.from_numpy(self._encode_state(state)),
                     volatile=flag).type(data_utils.Tensor)
        x = self.fc1(x)
        return self.output(x).view(n, self.num_hunters, -1)
        # return x

    def _encode_state(self, state):
        state = state[:, :, :]
        state = state.reshape(state.shape[0], -1)
        return state


    def select_action(self, Q_vec):
        sample = np.random.random()
        eps_threshold = self.eps_end + (self.eps_start - self.eps_end) * \
            np.exp(-1. * self._steps / self.eps_decay)
        self._steps += 1
        # if sample > eps_threshold:
        if True:
            if self.use_cuda:
                return Q_vec.data.cpu().max(1)[1].numpy().reshape(self.num_hunters, )
            else:
                return Q_vec.data.max(1)[1].numpy().reshape(self.num_hunters, )
        else:
            return np.random.randint(self.num_actions, size=(self.num_hunters, ))


class Policy(Model):
    def __init__(self, args):
        super(Policy, self).__init__(args)
        self.to_score = nn.Sequential(nn.Linear(self.num_states, self.hidden_dim), nn.Tanh(
        ), nn.Linear(self.hidden_dim, self.num_actions))
        self.to_value = nn.Sequential(nn.Linear(self.num_states, self.hidden_dim), nn.Tanh(
        ), nn.Linear(self.hidden_dim, self.num_actions))

        self._reset()

    def _init_weights(self):
        pass

    def forward(self, state):
        x = self._encode_state(state)
        score = self.to_score(x)
        value = self.to_value(x)
        prob_score = F.softmax(score)
        action = self._select_action(prob_score).detach()
        log_prob = F.log_softmax(score)
        log_prob = torch.gather(log_prob, 1, action)
        return log_prob, action.data[0, 0], value

    def _select_action(self, prob_score):
        """Sample action from multinomial distribution
            Parameters
            ----------
            prob_score: probability score of actions, FloatTensor
            Returns
            -------
            action matrix
        """
        return torch.multinomial(prob_score, 1)

    def _encode_state(self, state):
        """Create One-hot Vector of Current State
            Parameters
            ----------
            state: input state
            Returns
            -------
            One-hot torch FloatTensor: (1, num_states)
        """
        return torch.eye(self.num_states)[state - 1].view(1, self.num_states)
