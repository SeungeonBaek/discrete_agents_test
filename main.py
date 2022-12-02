import serversetup
serversetup.server_setup()

import os, sys
from datetime import datetime
from typing import Dict

import numpy as np
from tensorboardX import SummaryWriter

if __name__ == "__main__":
	sys.path.append(os.getcwd())

from utils.rl_logger import RLLogger
from utils.rl_loader import RLLoader

from utils.state_logger import StateLogger


def main(env_config: Dict,
         agent_config: Dict,
         rl_config: Dict,
         rl_custom_config: Dict,
         learned_model_path: str,
         result_path: str,
         rl_logger: RLLogger,
         rl_loader: RLLoader,
         state_logger: StateLogger):
    # Env
    env, env_obs_space, env_act_space = rl_loader.env_loader()
    print(f"env_name : {env_config['env_name']}, obs_space : {env_obs_space}, act_space : {env_act_space}")


    if len(env_obs_space) > 1:
        obs_space = 1
        for space in env_obs_space:
            obs_space *= space
    else:
        obs_space = env_obs_space[0]

    act_space = env_act_space

    # Agent
    RLAgent = rl_loader.agent_loader()
    Agent = RLAgent(agent_config, obs_space, act_space)
    if rl_custom_config['use_learned_model']:
                Agent.load_models(path=learned_model_path + "score_" + str(rl_custom_config['learned_model_score']) + "_model")
    else:
        pass

    print('agent_name: {}'.format(agent_config['agent_name']))

    # define max step
    if 'highway-v0' in env_config['env_name']: # vanilla highway and custom highway
        max_step = env.config['duration'] * env.config['policy_frequency']
        feature_range_x = env.config['observation']['features_range']['x']
        feature_range_y = env.config['observation']['features_range']['y']
        feature_range_vx = env.config['observation']['features_range']['vx']
        feature_range_vy = env.config['observation']['features_range']['vy']

    else:
        max_step = env_config['max_step']

    # csv logging
    if rl_config['csv_logging']:
        state_logger.initialize_memory(env_config['max_episode'], max_step, act_space)

    total_step = 0
    max_score = 0
    

    for episode_num in range(1, env_config['max_episode']):
        episode_score = 0
        episode_step = 0
        done = False

        prev_obs = None
        prev_action = None
        episode_rewards = []

        obs = env.reset()
        #print(obs[0][3])
        #print(obs[1][3])
        if env_config['env_name'] == 'custom_highway-v0':
            obs = np.array(obs[0])
        else:
            obs = np.array(obs)

        obs = obs.reshape(-1)
        if rl_custom_config['use_prev_obs']:
            enlonged_obs = np.concatenate((obs, obs))

        action = None

        while not done:
            if env_config['render']:
                env.render()
            episode_step += 1
            total_step += 1

            if rl_custom_config['use_prev_obs']:
                action, action_values = Agent.action(enlonged_obs, rl_custom_config['use_learned_model'])
            else:
                action, action_values = Agent.action(obs, rl_custom_config['use_learned_model'])

            # obs parsing per env
            if env_config['env_name'] == 'LunarLander-v2' or env_config['env_name'] == 'highway-v0':
                obs, reward, done, _ = env.step(action)
            elif env_config['env_name'] == 'custom_highway-v0':
                obs, reward, done, _ = env.step(action)
                obs, origin_obs = obs[0], obs[1]
            elif env_config['env_name'] == None: # Todo
                obs, reward, terminated, truncated, _ = env.step(action)
                done = terminated or truncated

            obs = np.array(obs)
            obs = obs.reshape(-1)

            if rl_custom_config['use_prev_obs']:
                if episode_step >= 2:
                    enlonged_obs = np.concatenate((prev_obs, obs))
                else:
                    enlonged_obs = np.concatenate((obs, obs))

            action = np.array(action)

            episode_score += reward
            episode_rewards.append(reward)

            # Save_xp
            reward_int = 0
            if rl_custom_config['use_learned_model']:
                pass # does not save the transition
            else:
                if episode_step >= 2:
                    if rl_custom_config['use_prev_obs']:
                        if Agent.extension_name == 'ICM' or Agent.extension_name == 'RND' or Agent.extension_name == 'NGU':
                            reward_int = Agent.get_intrinsic_reward(prev_enlonged_obs, enlonged_obs, prev_action)
                        Agent.save_xp(prev_enlonged_obs, enlonged_obs, reward+reward_int, prev_action, done)
                    else:
                        if Agent.extension_name == 'ICM' or Agent.extension_name == 'RND' or Agent.extension_name == 'NGU':
                            reward_int = Agent.get_intrinsic_reward(prev_obs, obs, prev_action)
                        Agent.save_xp(prev_obs, obs, reward+reward_int, prev_action, done)

            if rl_custom_config['use_prev_obs']:
                prev_enlonged_obs = enlonged_obs

            prev_obs = obs
            prev_action = action

            if episode_step >= max_step:
                done = True
                continue
            
            if Agent.extension_name == 'ICM' or Agent.extension_name == 'RND' or Agent.extension_name == 'NGU':
                rl_logger.step_logging(Agent, reward_int, rl_custom_config['use_learned_model'])
            else:
                rl_logger.step_logging(Agent, rl_custom_config['use_learned_model'])

            if rl_config['csv_logging']:
                state_logger.step_logger(episode_num, episode_step, origin_obs, obs, action_values, action)

        env.close()

        rl_logger.episode_logging(Agent, episode_score, episode_step, episode_num, episode_rewards, inference_mode=rl_custom_config['use_learned_model'])

        if rl_config['csv_logging']:
            state_logger.episode_logger(episode_num, episode_score, episode_step)
            state_logger.save_data(episode_num)

        if episode_score > max_score:
            print(f"result_path: {result_path}")
            if os.name == 'nt':
                Agent.save_models(path=result_path + "\\", score=round(episode_score, 3))
            elif os.name == 'posix':
                Agent.save_models(path=result_path + "/", score=round(episode_score, 3))
            else:
                raise ValueError("what's the os??")
            max_score = episode_score

        print('epi_num : {episode}, epi_step : {step}, score : {score}, mean_reward : {mean_reward}'.format(episode= episode_num, step= episode_step, score = episode_score, mean_reward=episode_score/episode_step))
        
    env.close()


if __name__ == '__main__':
    from agent_env_config import env_agent_config
    """
    Env
    1: LunarLander-v2, 2: procgen, 3: highway, 4: custom-highway

    Agent
     1: DQN,     2: ICM_DQN,      3: RND_DQN,      4: NGU_DQN
     5: PPO,     6: MEPPO
     7: SAC,     8: TQC_SAC
     9: QR_DQN, 10: ICM_QR_DQN   11: RND_QR_DQN,  12: NGU_QR_DQN
    13: IQN,    14: QUOTA,
    15: RAINBOW 16: ICM_RAINBOW, 17: RND_RAINBOW, 18: NGU_RAINBOW
    19: Agent-57
    20: REDQ,   21: ICM_REDQ,    22: RND_REDQ,    23: NGU_REDQ
    """

    env_switch = 4
    agent_switch = 11

    env_config, agent_config = env_agent_config(env_switch, agent_switch)

    rl_config = {'csv_logging': False, 'wandb': False, 'tensorboard': False}
    rl_custom_config = {'use_prev_obs': False, 'use_learned_model': False,'learned_time': '2022-11-29_14-58-22', 'learned_model_score': 61.283}

    parent_path = str(os.path.abspath(''))
    if rl_custom_config['use_learned_model']:
        time_string = rl_custom_config['learned_model_time']
    else:
        time_string = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')

    result_path = parent_path + '/results/{env}/{agent}_{extension}_result/'.format(env=env_config['env_name'], agent=agent_config['agent_name'], extension=agent_config['extension']['name']) + time_string
    if os.name == 'nt':
        learned_model_path = parent_path + f"\\results\\{env_config['env_name']}\\{agent_config['agent_name']}_{agent_config['extension']['name']}_result\\" + rl_custom_config['learned_time'] + "\\"
        data_save_path = parent_path + f"\\results\\{env_config['env_name']}\\{agent_config['agent_name']}_{agent_config['extension']['name']}_result\\" + time_string + '\\'
    elif os.name == 'posix':
        learned_model_path = parent_path + f"/results/{env_config['env_name']}/{agent_config['agent_name']}_{agent_config['extension']['name']}_result/" + rl_custom_config['learned_time'] + "/"
        data_save_path = parent_path + f"/results/{env_config['env_name']}/{agent_config['agent_name']}_{agent_config['extension']['name']}_result/" + time_string + '/'

    summary_writer = SummaryWriter(result_path+'/tensorboard/')
    if rl_config['wandb'] == True:
        import wandb
        wandb_session = wandb.init(project="RL-test-densityC", job_type="train", name=time_string)
    else:
        wandb_session = None

    rl_logger = RLLogger(agent_config, rl_config, summary_writer, wandb_session)
    rl_loader = RLLoader(env_config, agent_config)
    
    state_logger = StateLogger(env_config, agent_config, rl_config, data_save_path)

    main(env_config, agent_config, rl_config, rl_custom_config, learned_model_path, result_path, rl_logger, rl_loader, state_logger)