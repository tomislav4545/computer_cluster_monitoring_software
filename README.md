## Prerequisites

Make sure you have Docker installed on your machine. If you haven't installed it yet, you can follow the instructions here: [Docker Installation Guide](https://docs.docker.com/get-docker/).

## Running app with Docker

To run the app using Docker, follow these simple steps:

1. Run the following commadns depending on your package manager:
   ```bash
    sudo apt-get install xauth xorg openbox
    sudo apt install x11-xserver-utils
    xhost +local:docker
    ``` 

2. Clone the repository:
    ```bash
    git clone git@github.com:tomislav4545/computer_cluster_monitoring_software.git
    cd computer_cluster_monitoring_software
    ```

3. Build the Docker image:
    ```bash
    docker build -t computer_cluster_monitoring_software .
    ```

4. Run the Docker container:
    ```bash
    docker run -v LOCAL_CONFIGS_PATH:/app/configs -v ~/.ssh:/root/.ssh -v /etc/hosts:/etc/hosts -e DISPLAY=$DISPLAY -v /tmp/.X11-unix:/tmp/.X11-unix -it computer_cluster_monitoring_software
    ```

    Replace `LOCAL_CONFIGS_PATH` with the path to your folder containing JSON config files.
