from __future__ import absolute_import, division, print_function

import torch
from torch import nn
from torch.nn import functional as F

from src.utils import obs_to_array, obs_array_to_tensor, updated_model


class RandomAgent(object):
    def __init__(self, action_space):
        self.action_space = action_space

    def act(self, obs, reward, done, mem):
        return self.action_space.sample()


class ControllerAgent(object):
    # TODO: move outside of ControllerAgent?
    class Controller(nn.Module):
        def __init__(self, v_dim, action_dim, m_dim):
            super(ControllerAgent.Controller, self).__init__()
            self.out = nn.Linear(v_dim+m_dim, action_dim)

        def forward(self, obs, mem=None):
            if mem is not None:
                mem = mem.squeeze(1)  # TODO: make it work for larger num_layers, etc.?
                obs = torch.cat((obs, mem), dim=-1)

            out = F.tanh(self.out(obs))

            # Scale the last two values to [0, 1]. # TODO: is there a nicer way to do this?
            out[:, -2] = (out[:, -2] + 1) / 2
            out[:, -1] = (out[:, -1] + 1) / 2

            return out

    def __init__(self, vae, v_dim, action_dim, rnn, m_dim, controller_params=None):
        self.controller = self.Controller(v_dim, action_dim, m_dim)
        self.vae = vae
        self.rnn = rnn

        if controller_params is not None:
            self.controller = updated_model(self.controller, controller_params)

        self.vae.eval()
        if self.rnn is not None:
            self.rnn.eval()

    def act(self, obs, reward, done, mem):
        with torch.no_grad():
            obs = obs_to_array(obs)  # Convert to resized np.array.
            obs = obs[None, :]  # Add dummy dimension for batch size.
            obs = obs_array_to_tensor(obs)  # Transform to normalized PyTorch tensor with channels first.
            enc_obs = self.vae.reparameterize(*self.vae.encode(obs))  # TODO: want sampling here?
            # TODO: also below, worth trying to have obs+mem and just obs at the same time?
            if mem is not None:
                action = self.controller(enc_obs, mem[0])  # Use only hidden state, not cell state.
            else:
                action = self.controller(enc_obs)
            if self.rnn is not None:
                _, _, _, mem = self.rnn(action.unsqueeze(1), enc_obs.unsqueeze(1), mem)  # Add dummy dim for seq len.
            return action.squeeze(0).numpy(), mem
