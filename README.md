# Easy-Wave

Code for generating awg sequences.

In particular, this code is meant to work with the Tektronix 5000 series, but could easilly be modified to work with other devices

# Setting up FTP
To use the FTP server you must be using nspyre.

A useful description for how to do this is given here: https://www.youtube.com/watch?v=nWpZkhXnhds&list=PLwjK9zBiuphdQ4TiEPdiyKzBa0G75NDBV . Please don't turn off your firewall. Set access for all users or for anonymous users. 

Test that your FTP server is working by going to ftp://[IP-Address-of-Tektronix-AWG]. 

Note that the IP address of the Tektronix may change. To fix this, you need to go to windows start -> control panel -> search for administrative tools -> Internet Information Services (IIS) Manager -> right click dil_fridge_ftp (under connections in left panel, AWG-3289382193, Sites, dil_fridge_ftp) -> Edit Bindings -> highlight current binding -> edit -> change IP address to the Tektronix IP address (IPv4 address found by typing ipconfig into the terminal) -> Ok
    - Check that the server is working again by doing firefox test above
