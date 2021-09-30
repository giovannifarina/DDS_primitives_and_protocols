from genericpath import exists
import configparser
import os.path
import logging

# LOAD LOGGING CONFIGURATION
LOG_Enabled = False
if os.path.isfile('DDS.ini'):
    
    config = configparser.ConfigParser()
    config.read('DDS.ini')

    # clear log file
    with open(config['LOG']['fileName'],'w') as fd:
        pass

    logger = logging.getLogger(config['LOG']['name'])
    logger.setLevel(int(config['LOG']['level']))
    fh = logging.FileHandler(config['LOG']['fileName'])
    logger.addHandler(fh)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    fh.setFormatter(formatter)

    logger.propagate = False

    LOG_Enabled = True