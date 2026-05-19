i want to create an app that collects details about VMs/Containers etc on several servers and then maintain a small set of wiki pages that detail what each vm/container does, where it sits, its type and basic stats.

I am thinking this would need to be split into several parts :

1. Discovery
1.1. SSH to each of a list of physical servers
1.2. Determine the type of server and if its a VM or a Container type system
1.3. Extract a list of all servers/containers
1.4. Extract any stats for each server/container
1.5. Feed data into next stage
2. Colation
2.1. Take data from previous step
2.2. If required create folders/information files for each server and the vm/containers
2.3. Take note of any missing information and request more info from next step
3. Additional documentions
3.1. Create blank pages for any missing infoamtion files
3.2. Produce a 'front page' that details what servers and vm/containers where found with links
3.3. Add warnings for any missing information
4. Wiki presentation
4.1. Display the WiKi and present some way to edit any pages that are missing data
4.2. Ensure all data is presented in a format that is as close as possible for all forms of container/vm


Config File :
If using PHP, then this should be JSON/YAML, if using Python, then TOML
Config is read on every run.
Contains an array of physical machines to scan, this includes Name/HostName/IP(if blank, use hostname to connect)/Login User/SSH Keyfile
Config is mounted read only into the app containers.

Access to each physical server is via SSH.
SSH keys are mounted RO into a single directory and referanced by there filename

Server types :
LXD
Docker
HyperV
XEN

All data is stored in plain markdown files using folders to seperate data.
i.e. a docker container 'MyMail' running on a physical server 'dev001.mynetwork.com' would have a folder structure approx like :
.
└── servers
    └── dev001.mynetwork.com
        └── docker
            └── mymail
                ├── DESCRIPTION.md
                ├── README.md
                └── SPEC.md



Wiki server :
Already have 'SilverBullet' Wiki running on the local network.
Maybe create another instance of this (or link into the existing one) to give a Wiki frontend with editing features.  This would save having to re-invent the wheel for wiki editing/display





Future expansions :
1. Add option to export a new list of servers to scan to be added to the config file
This would allow the system to detect that a physical server containing a VM that then has docker images
This extension would replicate the existing server array and add a new 'server' for the VM containing the docker system.

