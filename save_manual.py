import os
import time
from selenium import webdriver
import json
import shutil
import configparser
import urllib
import urllib.request
from collections import OrderedDict
from selenium.common.exceptions import StaleElementReferenceException
import logging
import traceback

logger = logging.Logger('SaveManual')

parser = configparser.ConfigParser()
parser.read('config.ini')

def ConfigSectionMap(section):
    dict1 = {}
    options = parser.options(section)
    for option in options:
        try:
            dict1[option] = parser.get(section, option)
            if dict1[option] == -1:
                DebugPrint("skip: %s" % option)
        except:
            print("exception on %s!" % option)
            dict1[option] = None
    return dict1


#This URL will be the URL that your login form points to with the "action" tag.
POST_LOGIN_URL = ConfigSectionMap('URLs')['login']
#This URL is the page you actually want to pull down with requests.
REQUEST_URL = ConfigSectionMap('URLs')['manual']
LOGIN_PASSWORD = ConfigSectionMap('Setup')['password']

# Setup Selenium Chrome Web Driver
chromedriver = ConfigSectionMap('Setup')['driverlocation']
os.environ["webdriver.chrome.driver"] = chromedriver

# root directory of where to store all of the files
car = ConfigSectionMap('Setup')['car']
base_path = ConfigSectionMap('Setup')['downloadlocation']
download_path = os.path.join(base_path, car) 
try:
    os.makedirs(download_path)
except:
    logger.debug('{} is where the manual will be saved'.format(download_path))

# these are the options for being able to save the page as pdf with selenium
appState = {
"recentDestinations": [
    {
        "id": "Save as PDF",
        "origin": "local"
    }
],
"selectedDestinationId": "Save as PDF",
"version": 2
}

profile = {'printing.print_preview_sticky_settings.appState':json.dumps(appState),'savefile.default_directory':download_path}
chrome_options = webdriver.ChromeOptions() 
chrome_options.add_experimental_option('prefs', profile) 
chrome_options.add_argument('--kiosk-printing')

def save_rs_content(driver, append_path, chapter, item_num):
    """Save the dvRSContent as html while also replacing the href links and image locations to the same directory
    as the html file
    
    The chapter will be saved as {item_num}_chapter
    
    driver (selenium.webdriver.Chrome)
    append_path (str): where to store the html file and images
    chapter (str): name of the chapter
    item_num (str): what number to name the file in the directory
    """
    ## get all images and image link references
    base_link = 'http://www.chiltonlibrary.com'
    rs_content = driver.find_element_by_id('dvRSContent')
    a_tags = rs_content.find_elements_by_tag_name('a')
    img_tags = rs_content.find_elements_by_tag_name('img')
    html = rs_content.get_attribute('innerHTML')
    time.sleep(1)
    
    replace_items = []
    download_links = []
    for a_tag in a_tags:
    # get a list of items to replace in the full html text
        href_string = a_tag.get_attribute('href')
        if not href_string:
            continue
        for item in href_string.split("'"):
            if item.endswith(('.pdf','.gif','.jpg')):
                download_links.append(base_link+item)
                replace_items.append((href_string, os.path.basename(item)))
                
    for img in img_tags:
        img_path = img.get_attribute('src')
        download_links.append(img_path)
        replace_items.append((img_path.replace(base_link,''), os.path.basename(img_path)))
        
    # download all images/pdfs
    for download_link in download_links:
        download_path = os.path.join(append_path,os.path.basename(download_link))
        urllib.request.urlretrieve(download_link, download_path)
        
    for replace_item in replace_items:
    # replace image reference items with relative links
        html = html.replace(replace_item[0], replace_item[1])
        
    html_file = os.path.join(append_path, '{:03}_{}.html'.format(item_num, chapter))
    with open(html_file, "w") as f:
    # write the html file
        f.write(html)
    

def item_set_by_id(driver, el_id, tag):
    item_list = driver.find_element_by_id(el_id)
    items = item_list.find_elements_by_tag_name(tag)
    item_set = set()
    for it in items:
        item_set.add(it.text)
    return item_set

def wait_for(condition_function, driver, pass_num=0):
    """Used to wait for a condition to complete
    """
    start_time = time.time()
    while time.time() < start_time + 30:
        if condition_function():
            return True
        else:
            time.sleep(0.1)
#     raise Exception(
#         'Timeout waiting for {}'.format(condition_function.__name__)
#     )
    ## otherwise refresh page and wait again
    if pass_num == 5:
    ## only try 5 times
        return
    current_url = driver.current_url
    driver.refresh()
    driver.get(current_url)
    time.sleep(3)
    wait_for(condition_function, driver, pass_num+1)
    
    
    
def click_through_to_new_page(driver, link, first_level=False):
    """Functionality for clicking through to the next page specified"""
    if not first_level:
        item_check = driver.find_element_by_id('dvRSContent')
    else:
    # there is no dvRSContent on the top level of TOC, so just hoping for the best
    # to load
        link.click()
        time.sleep(20)
        return True
    link.click()

    def link_has_gone_stale():
    # wait for beingunable to access dvRSContent because we're not on the same page anymore
        try:
            # poll the link with an arbitrary call
            item_check.find_elements_by_tag_name('h1') 
            return False
        except StaleElementReferenceException:
            return True

    wait_for(link_has_gone_stale, driver)
    
def back_a_page(driver):
    """Functionality for going back a page"""
    time.sleep(2)
    item_check = driver.find_element_by_id('dvRSContent')
    driver.back()

    def link_has_gone_stale():
        try:
            # poll the link with an arbitrary call
            item_check.find_elements_by_tag_name('h1') 
            return False
        except StaleElementReferenceException:
            return True

    wait_for(link_has_gone_stale, driver)

def print_or_parse_v2(driver, parent_items, item_num, append_path, nest_level=1, 
                      keep_continue=False, first_level=False, pass_chapters=None):
    """Recursive function to either print the page or go deeper
    
    ARGS: 
        driver (selenium.webdriver.Chrome)
        parent_items: list of selenium elements from the table of contents
        item_num (int): number it will be in the directory context
        append_path (str): path where this page is in the table of contents context
        nest_level (int): how far nested in the table of contents we are
        keep_continue (bool): This is for when this might have failed and whether check
            for certain chapters to be skipped or not
        first_level (bool): Is this the first nest? Probably should have used nest_level==1
            but too late now
        pass_chapters (list of str): the very last nest that was successfully printed so we can
            figure out where to pick up from where we left off last
    """
    item = parent_items[item_num]
    
    chapter_dirty = item.text
    chapter = chapter_dirty.replace('/', '-')
    # replace all "/" in the chapter name otherwise it will think it was spanning multiple directories
    
    if not keep_continue:
        if chapter in pass_chapters:
        # if chapter is part of the latest successful nest
            if chapter == pass_chapters[-1]:
            # check until we find the very last successful item and set so we never have to check
            # in this iteration again
                keep_continue = True
        else:
        # otherwise skip parsing through this chapter
            logger.debug('Skipping {}--{}'.format(append_path, chapter))
            return keep_continue
        
    click_through_to_new_page(driver, item, first_level)
    
    print('{} page Loaded'.format(chapter))
            
    # get list of links if it exists
    link_list = driver.find_element_by_id('dvRSContent')
    link_items = link_list.find_elements_by_class_name('linkList')
    link_itemsv2 = link_list.find_elements_by_class_name('linkDown')

    if link_itemsv2:
    # if there is a list of link items representing the sub chapters
        # create a new directory
        save_folder = os.path.join(append_path, '{:03}_{}'.format(item_num, chapter))
        try:
            os.makedirs(save_folder)
        except:
            logger.debug(save_folder)
        for i in range(1, len(link_itemsv2), 2):
        # for some reason in the list of elements, it duplicates?
        # so link_items_v2[0] is the same as link_items_v2[1], but only 
        # link_items_v2[1] has the working link
            # make sure to pull the current working links again since we might have come back from
            # a different link and dont have the latest element references
            link_list2 = driver.find_element_by_id('dvRSContent')
            link_items2 = link_list2.find_elements_by_class_name('linkList')
            link_items2v2 = link_list2.find_elements_by_class_name('linkDown')
            
            logger.debug('Deeper into {}'.format(chapter))
            keep_continue = print_or_parse_v2(driver, link_items2v2, i, save_folder, 
                                              nest_level+1, keep_continue, pass_chapters=pass_chapters)
    else:
        logger.debug('printing page')
        time.sleep(3)
        ## old code when i was printing to pdf
#         driver.execute_script('window.print();')
#         link_list.screenshot(os.path.join(download_path,'page.png'))
#         file_type = '.pdf'
#         save_file = [f for f in os.listdir(download_path) if f.endswith(file_type)].pop()
#         save_file = [f for f in os.listdir(download_path) if f.endswith('pdf')].pop()
#         old_loc = os.path.join(download_path, save_file)
#         new_loc = os.path.join(append_path, '{}_{}'.format(item_num, chapter+file_type))
#         shutil.move(old_loc, new_loc)
        save_rs_content(driver, append_path, chapter, int(item_num))
        
    back_a_page(driver)
    return keep_continue

def get_last_found_item(download_path):
    """Find the last successful page downloaded and it's nest structure"""
    
    last_item_path = []
    item_dict = {}
    for item in os.listdir(download_path):
    # get list of html / toc list
        if item.startswith('.'):
        # skip hidden files/folder
            continue
        if not '_' in item:
            continue
        item_dict.update({
                int(item.split('_', 1)[0]): item.split('_', 1)[1]
            })
    ordered_items = OrderedDict(sorted(item_dict.items()))

    # if last item ends in .html, then we hit the end, else go in the folder more
    if not ordered_items:
        return [], 0
    last_index = next(reversed(ordered_items))
    last_item_path.append(ordered_items[last_index].replace('.html','')) ## get rid of .html extension
    if ordered_items[last_index].endswith('.html'):
        return last_item_path, last_index
    
    # otherwise go into next
    next_dir = os.path.join(download_path, '{:03}_{}'.format(last_index, ordered_items[last_index]))
    extra_items, random_index = get_last_found_item(next_dir)
    last_item_path.extend(extra_items)
    return last_item_path, last_index


consecutive_failures = 0
while True:

    print('Consecutive Failures: {}, Loop Restarted'.format(consecutive_failures))
    try:
    # keep restarting when it fails
    
        # login
        driver = webdriver.Chrome(chromedriver, chrome_options=chrome_options)  
        driver.get(POST_LOGIN_URL)
        time.sleep(2)
        login_element = driver.find_element_by_class_name("form-control")
        login_element.send_keys(LOGIN_PASSWORD)
        time.sleep(2)
        driver.find_element_by_class_name('btn-block').click()

        # get to start 
        time.sleep(2)
        driver.get(REQUEST_URL)
    
        html_list = driver.find_element_by_id('dvRepairTree')
        items = html_list.find_elements_by_tag_name('li')
        items_set = item_set_by_id(driver, 'dvRepairTree','li')

        last_good_items, start_from = get_last_found_item(download_path)
        if last_good_items:
            keep_continue = False
        else:
            keep_continue = True

        print('Skipping all these chapters'.format(str(last_good_items)))
        print(last_good_items)
        print('Starting with chapter num: {}'.format(start_from))

        for i in range(start_from,len(items)):
            time.sleep(5)
            driver.get(REQUEST_URL)
            time.sleep(5)
            consecutive_failures = 0
            html_list2 = driver.find_element_by_id('dvRepairTree')
            items2 = html_list2.find_elements_by_tag_name('li')
            print('Going in')
            keep_continue = print_or_parse_v2(driver, items2, i, download_path, 1, 
                                              keep_continue, first_level=True, pass_chapters=last_good_items)
        break

    except:
    # fail if 10+ consecutive failures (driver probably broken and need to log in again)
        driver.close()
        traceback.print_exc()
        consecutive_failures += 1
        if consecutive_failures >= 10:
            break


    


    
    