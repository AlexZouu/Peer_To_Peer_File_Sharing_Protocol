import argparse
import json
from pathlib import Path
import threading
from queue import Queue
from P2PService import requestFile, handleRequest
from RDT.ReliableDataTransfer import rdtReceive
from API.TrackerAPI import POST_user, GET_availableFiles, GET_usersWithFile, PUT_file, DELETE_file, DELETE_user


def printCommandList():
  """
  Prints the list of commands the user can use
  """
  print('Usage:')
  print('files\t\t\t: Get the list of available files to download')
  print('download <filename>\t: Download the specified file')
  print('add <filename>\t\t: Add a file to the user')
  print('\tNote: Only use this if you manually add a file either by manually creating / copying / moving a file into the associated User folder')
  print('\t      Do not use this if you just downloaded a file using the "download" command')
  print('remove <filename>\t\t: Delete a file from the user')
  print('quit\t\t\t: Close application')
  print('help\t\t\t: Print list of available commands')


def parseArgs():
  """
  Handles reading in command line arguments

  Returns:
    (int): The port to connect to
    (str): The nickname of the user
  """
  parser = argparse.ArgumentParser()    # Create the parser

  # Add all the args
  parser.add_argument('port', help='The port you wish to connect with', type=int)
  parser.add_argument('nickname', help='The nickname you wish to use', type=str)

  args = parser.parse_args()    # Parse the args

  port = args.port

  if port < 2000 or port > 49000 or port % 100 != 0:   # Handle if the port is not valid
    print('ERROR: Port number must be at least 2000, less than 49000, and must be in intervals of 100')
    return None, None

  return args.port, args.nickname.lower()


def getAsyncInput(command):
  """
  The function to get input commands from the user

  Args:
    command (dict): The variable used to get the command back to the main thread
  """
  print('Input your next command:')

  userInput = input().lower().strip()   # Get the user input, convert it to lowercase and strip leading and trailing whitespaces
  if userInput == '': userInput = 'invalid'   # If the user input doesn't exist, set it to invalid
  splitInput = userInput.split()    # Split the input on whitespaces
  
  if userInput in ['files', 'quit', 'help']: command['command'] = userInput   # If the input is one of the single word commands, set the command to it
  elif splitInput[0] in ['download', 'add', 'remove']:    # If it's one of the commands with args
    inputLen = len(splitInput)    # Get the number of words

    if inputLen == 2:   # If the user added two words
      command['command'] = splitInput[0]    # Set the command
      command['filename'] = splitInput[1].lower()   # and the filename
    else:   # If the number of words is not 2
      print('Invalid arguments')    # Print an error message
      print(f'Usage: {splitInput[0]} example_file.txt')
  else:
    command['command'] = userInput    # If the command doesn't exist, we still need to set it. The main thread will handle it
    print('Unknown command. Type "help" to get a list of commands')


def downloadFile(sPort, filename, availablePorts, nickname):
  """
  Download a specific file

  Args:
    sPort (int): The main port the user is assigned to
    filename (str): The name of the file to download
    availablePorts (Queue): A queue of all the available ports for the user to use
    nickname (str): The nickname of the user
  """
  path = Path(f'Users\\{nickname}\\{filename}')
  if path.is_file():
    print (f'Error: You already have {filename}')
    return 
  
  peers = GET_usersWithFile(sPort, filename)

  fileRequestThread = threading.Thread(target=requestFile, args=[availablePorts, peers, filename, nickname])    # Create the thread that actually handles the download process
  fileRequestThread.start()   # Start it

  print(f'Downloading {filename}')


def peerToPeer(port, nickname):
  """
  The main function handling the peer to peer interactions

  Args:
    port (int): The main port the user is assigned to
    nickname (str): The nickname assigned to the user
  """
  try:
    POST_user(port, nickname)    # Try to initiate the user
  except Exception as e: 
    print(f'Error: {e}')
    return

  availablePorts = Queue(maxsize=99)    # Create the queue of the available ports
  # These ports are used for paralellism, as you can only have one socket on each port receiving messages
  # This is also why the ports need to be 100 apart. The 00 port is the main port responsible for simple queries
  # while the 01-99 ports are used for the bulk of the file transfering

  for i in range(port + 1, port + 100): availablePorts.put(i)   # Add the port numbers 01-99 to the queue

  printCommandList()    # Print the list of commands
  
  command = {}    # The command the user inputs
  inputThread = None    # The thread for getting user input

  while True:
    if inputThread is None:   # If there is no thread waiting for user input, start one
      inputThread = threading.Thread(target=getAsyncInput, args=[command])
      inputThread.start()
    
    try:
      if command != {}:   # If the command exists
        match command['command']:   # Determing which command it is and run the associated function
          case 'files': GET_availableFiles(port)
          case 'download': downloadFile(port, command['filename'], availablePorts, nickname)
          case 'add': PUT_file(port, command['filename'], nickname)
          case 'remove': DELETE_file(port, command['filename'], nickname)
          case 'help': printCommandList()
          case 'quit':
            DELETE_user(port)
            break

        command = {}    # Reset the command
        inputThread = None    # Set the input thread to None
    except Exception as e: 
      print(f'Error: {e}')
      command = {}    # Reset the command
      inputThread = None    # Set the input thread to None

    sPort, message = rdtReceive(0, port, timeout=1)   # See if there's any requests from other users
    # The timeout of 1 means it will only block the main thread for 1 second waiting for requests
    # If times up and nothing's been received, it will return None

    if sPort:   # If we got a message, start a thread to handle the request so the main thread can continue to handle user commands and other requests
      requestThread = threading.Thread(target=handleRequest, args=[availablePorts, sPort, json.loads(message), f'Users\\{nickname}\\'])
      requestThread.start()


def main():
  """
  The main entry point to the program
  """
  port, nickname = parseArgs()    # Get the args

  if port is None: return

  peerToPeer(port, nickname)    # Start the peer to peer service


if __name__ == '__main__': main()