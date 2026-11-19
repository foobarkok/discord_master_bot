import importlib
import sys
from os import environ
from pathlib import Path

import dotenv

dotenv.load_dotenv()

for name in sys.argv[1:]:
    try:
        module = importlib.import_module(f"bots.{name}")
        break
    except ModuleNotFoundError:
        print(f"module {name} does not exists.")

bot = module.create_bot()
bot.run(environ[module.token_name])
