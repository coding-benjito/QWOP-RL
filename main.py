import os
import time

import click
import tensorflow as tf
from stable_baselines import ACER
from stable_baselines.common.callbacks import CheckpointCallback
from stable_baselines.common.vec_env import SubprocVecEnv

from game.env import ACTIONS
from game.env import QWOPEnv
from pretrain import imitation_learning
from pretrain import recorder

# from agents.ACERfD import ACER

# Training parameters
MODEL_NAME = 'test_model'
TRAIN_TIME_STEPS = 100000 * 3
REPLAY_START = 2000
BUFFER_SIZE = 3000
REPLAY_RATIO = 3
LEARNING_RATE = 7e-4 * (1 / 350)
LR_SCHEDULE = 'linear'
MODEL_PATH = os.path.join('models', MODEL_NAME)
TENSORBOARD_PATH = './tensorboard/'

# Checkpoint callback
checkpoint_callback = CheckpointCallback(
    save_freq=100000, save_path='./logs/', name_prefix=MODEL_NAME
)

# Imitation learning parameters
RECORD_PATH = os.path.join('pretrain', 'kuro_1_to_5')
N_EPISODES = 10
N_EPOCHS = 500
PRETRAIN_LEARNING_RATE = 0.00001  # 0.0001


def get_new_model():

    # Define policy network
    policy_kwargs = dict(act_fun=tf.nn.relu, net_arch=[256, 128])

    # Initialize env and model
    env = QWOPEnv()
    model = ACER(
        'MlpPolicy',
        env,
        policy_kwargs=policy_kwargs,
        verbose=1,
        tensorboard_log=TENSORBOARD_PATH,
    )

    return model


def get_existing_model(model_path):

    print('--- Training from existing model', model_path, '---')

    # Load model
    model = ACER.load(model_path, tensorboard_log=TENSORBOARD_PATH)

    # Set environment
    env = SubprocVecEnv([lambda: QWOPEnv()])
    model.set_env(env)

    return model


def get_model(model_path):

    if os.path.isfile(model_path + '.zip'):
        model = get_existing_model(model_path)
    else:
        model = get_new_model()

    return model


def run_train(model_path=MODEL_PATH):

    model = get_model(model_path)
    model.learning_rate = LEARNING_RATE
    model.buffer_size = BUFFER_SIZE
    model.replay_start = REPLAY_START
    model.replay_ratio = REPLAY_RATIO
    model.lr_schedule = LR_SCHEDULE

    # Train and save
    t = time.time()

    model.learn(
        total_timesteps=TRAIN_TIME_STEPS,
        callback=checkpoint_callback,
        reset_num_timesteps=False,
    )
    model.save(MODEL_PATH)

    print(f"Trained {TRAIN_TIME_STEPS} steps in {time.time()-t} seconds.")


def print_probs(model, obs):

    # Print action probabilities
    probs = model.action_probability(obs)
    topa = sorted(
        [(prob, kv[1]) for kv, prob in zip(ACTIONS.items(), probs)],
        reverse=True,
    )[:3]
    print(
        'Top 3 actions - {}: {:3.0f}%, {}: {:3.0f}%, {}: {:3.0f}%'.format(
            topa[0][1],
            topa[0][0] * 100,
            topa[1][1],
            topa[1][0] * 100,
            topa[2][1],
            topa[2][0] * 100,
        )
    )


def run_test():

    # Initialize env and model
    env = QWOPEnv()
    model = ACER.load(MODEL_PATH)

    input('Press Enter to start.')

    time.sleep(1)

    for _ in range(100):

        # Run test
        t = time.time()
        done = False
        obs = env.reset()
        while not done:

            action, _states = model.predict(obs, deterministic=False)
            # print_probs(model, obs)
            obs, rewards, done, info = env.step(action)

        print(
            "Test run complete: {:4.1f} in {:4.1f} seconds. Velocity {:2.2f}".format(
                env.previous_score,
                time.time() - t,
                env.previous_score / (time.time() - t),
            )
        )

        time.sleep(1)

        # Admire the finish
        if env.previous_score >= 100:
            time.sleep(5)

    input('Press Enter to exit.')


@click.command()
@click.option(
    '--train',
    default=False,
    is_flag=True,
    help='Run training; will train from existing model if path exists',
)
@click.option('--test', default=False, is_flag=True, help='Run test')
@click.option(
    '--record',
    default=False,
    is_flag=True,
    help='Record observations for pretraining',
)
@click.option(
    '--imitate',
    default=False,
    is_flag=True,
    help='Train agent from recordings; will use existing model if path exists',
)
def main(train, test, record, imitate):
    """Train and test an agent for QWOP."""

    if train:
        run_train()
    if test:
        run_test()

    if record:
        env = QWOPEnv()
        recorder.generate_obs(env, RECORD_PATH, N_EPISODES)

    if imitate:
        model = get_model(MODEL_PATH)
        imitation_learning.imitate(
            model, RECORD_PATH, MODEL_PATH, PRETRAIN_LEARNING_RATE, N_EPOCHS
        )

    if not (test or train or record or imitate):
        with click.Context(main) as ctx:
            click.echo(main.get_help(ctx))


if __name__ == '__main__':
    main()
