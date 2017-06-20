import time
import numpy as np
import argparse
import random
import collections

import torch
import torch.nn as nn
import torch.optim as optim
import torch.nn.functional as F
from torch.autograd import Variable
from env.cliff_walking import CliffWalkingEnv
import model_zoo
import data_utils


def render_single(model, env):
    episode_reward = 0
    state = env.reset()
    done = False
    action = None
    flag = None
    if torch.cuda.is_available():
        flag = False
    else:
        flag = True
    while not done:
        env.render(animation=flag)
        time.sleep(0.25)
        if torch.cuda.is_available():
            state_vec = model(np.asarray(state, dtype=int)
                              * np.ones(1, dtype=int))
            action = int(state_vec.data.cpu().max(1)[1].numpy())
        else:
            state_vec = model(np.asarray(state, dtype=int)
                              * np.ones(1, dtype=int))
            action = int(state_vec.data.max(1)[1].numpy())
        state, reward, done = env.step(action)
        episode_reward += reward
    # env.render()
    # time.sleep(0.25)
    env.step(action)
    print("Episode reward: %f" % episode_reward)
    f = open('output.txt', 'a')
    f.write("Episode_reward: %s" % str(episode_reward))
    f.close()


class ReplayMemory(object):

    def __init__(self, capacity):
        self.capacity = capacity
        self.memory = []
        self.position = 0

    def push(self, *args):
        """Saves a transition."""
        if len(self.memory) < self.capacity:
            self.memory.append(None)
        self.memory[self.position] = args
        self.position = (self.position + 1) % self.capacity

    def sample(self, batch_size):
        return random.sample(self.memory, batch_size)

    def __len__(self):
        return len(self.memory)


def main(args):
    env = CliffWalkingEnv((args.grid_shape, args.grid_shape))
    args.num_states = int(env.nS)
    args.num_actions = int(env.nA)
    args.use_cuda = data_utils.use_cuda
    memory = ReplayMemory(args.memo_capacity)

    model = model_zoo.DQN(args)
    if data_utils.use_cuda:
        model.cuda()
    optimizer = optim.RMSprop(model.parameters())

    open('loss.txt', 'w').close()
    floss = open('loss.txt', 'a')

    for i in range(args.num_episodes):
        steps = 0
        total_reward = 0
        print("Episode: %d" % i)
        current_state = env.reset()
        done = False
        while not done:
            current_vec = model(np.asarray(
                current_state, dtype=int) * np.ones(1, dtype=int))
            action = model.select_action(current_vec)
            steps += 1
            # print(action.numpy())
            next_state, reward, done = env.step(action)
            total_reward += reward
            if done:
                next_state = None
            memory.push(current_state, action, next_state, reward)
            current_state = next_state
            if len(memory.memory) >= args.batch_size:
                transitions = np.asarray(memory.sample(args.batch_size))
                current_batch = transitions[:, 0].astype(int)
                action_batch = Variable(torch.from_numpy(
                    transitions[:, 1].astype(int))).unsqueeze(1)
                next_batch = transitions[:, 2].astype(int)
                reward_batch = Variable(
                    torch.from_numpy(transitions[:, 3])).float()

                non_final_mask = data_utils.ByteTensor(
                    (next_batch != None).astype(int).tolist())
                non_final_states = next_batch[next_batch != None]
                current_Q_vec = model(current_batch).gather(1, action_batch)
                next_Q_vec = Variable(torch.zeros(
                    args.batch_size).type(data_utils.Tensor))
                next_Q_vec[non_final_mask] = model(non_final_states).max(1)[0]
                target = next_Q_vec * args.gamma + reward_batch
                loss = F.smooth_l1_loss(current_Q_vec, target)
                optimizer.zero_grad()
                loss.backward()
                optimizer.step()
                if (steps % 500 == 0):
                    if torch.cuda.is_available():
                        print("Loss: ", steps, loss)
                        floss.write("Step: %d Loss: %s\n" %
                                    (steps, str(loss.data.cpu().numpy())))
                    else:
                        print("Loss: ", steps, loss)
                        floss.write("Step: %d Loss: %s\n" %
                                    (steps, str(loss.data.numpy())))
                if (steps % 2500 == 0):
                    break
        print("Finish at ", steps)
        print("Reward: ", total_reward)
        floss.write("Finished at: %d\n" % steps)
        floss.write("Reward: %s\n" % str(total_reward))
    floss.close()
    render_single(model, env)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--num_episodes', type=int,
                        default=1, help='Number of episodes to train')
    parser.add_argument('--gamma', type=float, default=0.99,
                        help='Decay rate of reward function')
    parser.add_argument('--lr', type=float, default=0.1,
                        help='Learning rate of update')
    parser.add_argument('--eps_start', type=float,
                        default=0.9, help="Epsilon init value")
    parser.add_argument('--eps_end', type=float,
                        default=0.05, help="Epsilon lower bound")
    parser.add_argument('--eps_decay', type=float, default=200,
                        help='Decay rate of epsilon')
    parser.add_argument('--memo_capacity', type=int,
                        default=1000, help='Memory capacity')
    parser.add_argument('--grid_shape', type=int,
                        default=10, help='grid shape')
    parser.add_argument('--batch_size', type=int,
                        default=128, help='Batch Size')
    args = parser.parse_args()

    main(args)