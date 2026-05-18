# Important Notes
I know a lot of this is written horribly. I did not plan adequately.\
This was supposed to be a pretty small thing and it ended up becoming way more than I expected.

I needed to stop at some point, and this state is what I decided.\
There are things I could fix, but I would be working on this forever if that was the case.

List of things I want to fix:
- The packets are being sent as strings split by a splitter string. Why I would do this? Who knows. It should be a JSONified dict. If I saw that in someone else's code, I'd be upset. 
- If a peer is forcefully shut or suddenly dropped, the entire system breaks. The tracker will assume the peer is still up, and continue to forward other peers to the lost peer. 
- To fix the aformentioned issue, the tracker should send a heartbeat periodically to each peer. If there's no response, drop the peer
- Also, if a peer fails to download a chunk after a specified time, it should attempt to download it from a different peer
- The file length should be stored in the tracker, not requested from one of the peers
- Somehow deal with files of the same name
- Deal with files that have been modified (tracker could store a hash of the file?)
- Better folder structure
- The program should stop you from assigning the same folder to multiple peers
- Much much more


# Installation Instructions
Clone the repository\
There are no external libraries needed. 

# RDT Intermediary
The intermediary program that forwards packets between hosts\
This can stay open forever no matter what

## Usage
run "python ./RDTIntermediary.py" while in the "Peer_To_Peer_File_Sharing_Protocol\src\RDT" directory

> python ./RDTIntermediary.py

### Flags
-d: Drop packets occasionally
> python ./RDTIntermediary.py -d

-c: Corrupt packets occationally
> python ./RDTIntermediary.py -c

-r: Reorder packets occasionally
> python ./RDTIntermediary.py -r

You can also combine the flags
> python ./RDTIntermediary.py -d -c -r


# Tracker
The program that tracks all the connected peers and the files they have

## Usage
run "python ./Tracker.py" in the "Peer_To_Peer_File_Sharing_Protocol\src" directory
> python ./Tracker.py

This can stay open forever unless a peer is forcefully closed, in which case this, along with every other peer, needs to be restarted


# P2P App
The program that handles individual peers

Do not force the peers to close by closing the terminal or with ctrl + c. If you wish to close the peer, use the quit command.\
If the peer is currently downloading or handling a request it will not close immediately. If you do force a peer to close, you need to restart every other peer and the tracker. 

## Usage
run "python ./P2PApplication.py \<portNumber\> \<nickname\>" in the "Peer_To_Peer_File_Sharing_Protocol\src" directory

> python ./P2PApplication.py 50000 test_user_1

\<portNumber\> refers to the port the user should connect to. It must be at least 50000 and in intervals of 100

\<nickname\> refers to the folder assigned to the peer in the Users folder. The program does not stop you from assigning the same folder to multiple peers, but please don't do that. If you use a nickname that doesn't already exist, it will create one for you

Once the peer is running, follow the command line instructions\
To simulate multiple peers, run this program simultaneously in multiple terminals


# Peers
Some information about the peers

Each peer is assigned a folder in the Users folder based on the nickname\
Inside the folders are all the files the peer has access to\
Please limit the file size to around 500 KB, as any bigger than that the program slows down dramatically\
As for file types, all should in theory work as files are being read and written in bytes

If you wish to add a file to the peer while it is connected, do so by either creating, copying, or moving a file into the\
associated User folder, then run the "add \<filename\>" command

If you wish to delete a file from the peer while it is connected, do so by running the "remove \<filename\>" command. It will automatically delete the file for you

If you wish to modify a file, please do not. If you really wish to do this, close all the peers with the file, modify all the files, then reconnect the peers


# How does the file transfer actually work?
A peer has a main port (the one set when the program is ran)\
E.g. 50000\
This port is ONLY used for simple queries such as communicating with the tracker and receiving requests from other peers

It also has a queue of available ports for parallelism (ports 1 - 99)\
E.g. 50001 - 50099\
These ports are used for handling requests from other peers and sending requests to other peers\
The sending and receiving of file chunks are done by these ports\
Once the main port receives a request, the request is handed off to one of these ports to actually process the request

When a peer requests a file, it contacts the centralized tracker program and gets a list of all the peers that have the file

It then creates a new thread and contacts the first peer in the list and gets the file size\
Once the peer has the file size, it determines the chunk size (fileSize / numPeersWithFile), and assigns a chunk to each peer

Then a new thread is created for each of the peers that has the file\
The original peer requests the associated chunk from each peer\
Once all the chunks have arrived, the peer reassembles the file and writes it

The peer then contacts the tracker program, informing it that it now has the file

### Example:
Peer 1 on port 50100 wants the file "text.txt"

It contacts the tracker (port 49999) using port 50100, and finds that Peers 2 (50200), 3 (50300), 4 (50400), and 5 (50500) have it

Peer 1 then starts a thread to handle the download using port 50101\
From here on out, Peer 1 doesn't use the main port 50100 for anything, instead using the additional ports (50101 - 50199)\
This frees the main port 50100 to handle other tasks

Peer 1 contacts Peer 2 (50200) using port 50101 to get the length of the file, which is 100 bytes\
Note: Peer 2 doesn't repond with it's main port (50200), instead it will respond using one of the additional ports\
Peer 1 chunks the file into 4 equal sized chunks, bytes 1-25, 26-50, 51-75, and 76-100\
It assigns one chunk to each peer with the file

Peer 1 opens 4 more children threads to send the request\
- Peer 1 contacts Peer 2 (50200) using port 50102, requesting bytes 1-25 of the file\
- Peer 1 contacts Peer 3 (50300) using port 50103, requesting bytes 26-50 of the file\
- Peer 1 contacts Peer 4 (50400) using port 50104, requesting bytes 51-75 of the file\
- Peer 1 contacts Peer 5 (50500) using port 50105, requesting bytes 76-199 of the file

Note: Once again, these peers don't respond on their main ports, they respond using on of their additional ports

Once all 4 threads finish, Peer 1 assembles the chunks it receives and writes it to the file

It then contacts the Tracker (49999) using port 50106, informing the Tracker that it has the "text.txt" file
  