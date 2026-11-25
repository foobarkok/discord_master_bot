import importlib
import sys
from os import environ

import dotenv

dotenv.load_dotenv()

module = None

for name in sys.argv[1:]:
    try:
        module = importlib.import_module(f"bots.{name}")
        break
    except ModuleNotFoundError:
        print(f"module {name} does not exists.")

if module is None:
    print("Please enter the bot's name.")
else:
    bot = module.create_bot()
    bot.run(environ[module.token_name])
