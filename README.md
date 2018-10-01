# Car-Manuals

## Pre-Requisites
* [Python3](https://realpython.com/installing-python/)
* [ChromeDriver](http://chromedriver.chromium.org/downloads) - install the correct one for the OS you are on. This lets the code simulate a chrome browser so we can open the links and save the html pages
* [Python Packages](requirements.txt) - See section below to install these requirements

### Installing Necessary Python Packages

After you have Python installed, you need to open the terminal window and navigate to the folder that contains this code. Install Python packages by running `pip install -r requirements.txt` or `pip3 install -r requirements.txt`

## Configurations (that need to be set)

These are the configuration variables that will be need to set in [config.ini](config.ini). If the variable isn't in the table below you don't need to worry about it.

| Variable | Example | Description |
| -------- | ------- | ----------- |
| Manual | http://www.chiltonlibrary.com/lh/Repair/Index/mwellxHWd41jTqW6Hz_-WcbGrDHo_M6255aZEKToVkwtr5RY1#root | The link to the repair manual for whatever car. Should be at the very first page of the table of contents and the screen is white |
| DriverLocation | /users/ky/downloads/chromedriver | Location of where you downloaded the ChromeDriver so the code can run |
| DownloadLocation | /users/ky/projects/links/ | Location of where you want the manual to be saved |
| Car | 2014 Buick LeSabre | Name of the car for the manual you are downloading |
| Password | - | Password for the site with the manual | 

## Run Instructions

After setting all the configurations and all pre-reqs, run the code from terminal by typing `python save_manual.py`