import sys
sys.path.append('../')

from RDT.ReliableDataTransfer import rdtSend, rdtReceive
from pathlib import Path
import json


TRACKER_PORT = 1025          # Port of the tracking program


def sendPacket(sPort, packet):
  """
  The function that handles actually sending the request

  Args:
    sPort (int): The main port number the user is assigned to
    packet (dict): The packet being sent to the tracker

  Return:
    (int): The port of the receiver
    (dict): The message returned by the receiver
  """
  rdtSend(sPort, TRACKER_PORT, 0, json.dumps(packet))   # Send a request to the tracker to get the available files
  receiverPort, message = rdtReceive(0, sPort, TRACKER_PORT)    # Receive the files

  messageDict = json.loads(message)

  if messageDict.get('status') != 'OK':
    raise Exception(messageDict.get('errMsg'))

  return receiverPort, messageDict


def POST_user(sPort, nickname):
  """
  The function in charge of initiating the user to the tracker

  Args:
    port (int): The main port number the user is assigned to
    nickname (str): The nickname of the user
  """
  filelist = []   # List of files the user has
  folderpath = Path('Users\\' + nickname)   # Get the path to the user's folder
  folderpath.mkdir(parents=True, exist_ok=True)   # If it doesn't exist, make it

  for filepath in folderpath.iterdir():   # For every file in the folder
    if filepath.is_file():    # If it's a file
      filelist.append(filepath.name.lower())    # Otherwise, add it to the list of files

  packet = {
    'request': 'POST_user',
  }

  if len(filelist) > 0: packet['files'] = filelist   # Add the files if they exist

  sendPacket(sPort, packet)


def GET_availableFiles(sPort):
  """
  Print all the available files to download

  Args:
    sPort (int): The main port number the user is connected to
  """
  packet = {
    'request': 'GET_availableFiles'
  }

  _, message = sendPacket(sPort, packet)

  files = message.get('files')

  print('Files available for download:')

  for filename in files: print(f'\t{filename}')   # Print all the files


def GET_usersWithFile(sPort, filename):
  """
  Get all the users with a specific file

  Args:
    sPort (int): The main port number the user is connected to
    filename (str): The name of the file to search by

  Return:
    (list): A list of all the users with the file
  """
  packet = {
    'request': 'GET_usersWithFile',
    'filename': filename
  }

  _, message = sendPacket(sPort, packet)

  return message.get('peers')


def PUT_file(sPort, filename, nickname):
  """
  Inform the tracker of a new available file

  Args:
    sPort (int): The main port the user is assigned to
    filename (str): The name of the new file
    nickname (str): The nickname of the user
  """
  folderpath = Path('Users\\' + nickname)   # The path of the user
  folderpath.mkdir(parents=True, exist_ok=True)

  for filepath in folderpath.iterdir():   # For each file in the folder
    if filename == filepath.name:   # If the filename matches the new file being added
      packet = {
        'request': 'PUT_file',
        'filename': filename
      }

      sendPacket(sPort, packet)
      print('File successfully added!')
      return
  
  print('ERROR: The file you tried to add does not exist')


def DELETE_file(sPort, filename, nickname):
  """
  Inform the tracker that a file no longer exists

  Args:
    sPort (int): The main port the user is assigned to
    filename (str): The name of the file being deleted
    nickname (str): The nickname of the user
  """
  if '\\' in filename or '/' in filename:   # If \ or / exists, return as we don't want to delete stuff in other directories
    print('Please do not try to delete stuff in other directories :(')
    return
  
  path = Path('Users\\' + nickname + '\\' + filename)   # Get the path to the file
  path.unlink(missing_ok=True)    # Delete the file. missing_ok means it won't throw an error if it doesn't exist

  packet = {
    'request': 'DELETE_file',
    'filename': filename
  }

  sendPacket(sPort, packet)   # Send the message informing the tracker the file is being removed

  print('File successfully deleted')


def DELETE_user(sPort):
  """
  Inform the tracker that the user is leaving

  Args:
    sPort (int): The main port the user is assigned to
  """
  packet = {
    'request': 'DELETE_user'
  }

  sendPacket(sPort, packet)

  print('Exiting')
  print('Warning: If the program does not exit immediately, there is likely a download / upload in progress, do not close the terminal')
  print('If the terminal is forcefully shut, you will have to close and reopen the terminals for the tracker and ALL peers')
  print('Note: The terminals need to be fully closed and reopened as threads may still be running in the background if only the main thread is stopped')