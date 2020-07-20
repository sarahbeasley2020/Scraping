# Import statements
import pandas as pd
import numpy as np
import csv
from parsel import Selector
from time import sleep
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
import json

company_data = {}

'''
Class to describe a given company
    @field: name: a string for the company name
    @field: description: a string for the company description
    @field: founders: a list of Founder objects
    @field: industries: a list of strings for different industries
    @field: website: a string for the website
    @field: lastStage: a string for the last stage of funding (eg. Series A)
    @field: linkedin: a string for the company's LinkedIn profile
    @field: location: a string for the company's location
'''
class Company:
    def __init__(self, companyName):
        self.name = companyName
        self.description = None
        self.founders = []
        self.industries = []
        self.website = None
        self.lastStage = None
        self.linkedin = None

    def toJson(self):
        return json.dumps(self, default=lambda o: o.__dict__)

'''
Class to describe a founder
    @field: name: a string for the founder's name
    @field: education: an list of education objects
    @field: experience: a list of experience objects
'''
class Founder:
    def __init__(self, founderName):
        self.name = founderName
        self.connections = None
        self.location = None
        self.education = []
        self.experience = []

'''
Class to help describe a founder's education
    @field: degree: a string to describe the degree objective
    @field: school: a string for the school attended
    @field: field: a string to describe the major
'''
class Education:
    def __init__(self, schoolName):
        self.school = schoolName
        self.degree = None
        self.field = None
'''
Class to help describe a founder's experience
    @field: companyName: a string to describe the company's name
    @field: title: a string to describe the title held
    @field: description: a string to describe the job description
'''
class Experience:
    def __init__(self, companyName):
        self.companyName = companyName
        self.title = None
        self.dates = None
'''
Loads the dataframe from Query 1 and Query 2 and merges + drops duplicates and NaNs
    @param: csv1: path to CSV 1 (formed by Query 1)
    @param: csv2: path to CSV 2 (formed by Query 2)
    @return: df1: a merged dataframe of csv1 and csv2
'''
def loadBacktestData(csv1, csv2):
    df1 = pd.read_csv(csv1)
    df2 = pd.read_csv(csv2)
    df1 = df1.append(df2)
    df1 = df1.drop_duplicates(subset=['Organization Name'])
    df1 = df1[df1.Founders.notna()]
    df1 = df1[df1.LinkedIn.notna()]
    df1 = df1.reset_index()
    for i in range(len(df1)):
        if df1.iloc[i].LinkedIn.count('about') > 0:
            df1['LinkedIn'][i] = df1['LinkedIn'][i].split('about')[0]
    return df1

'''
Method to set up and log into the LinkedIn using chromedriver
    @param: driverPath: path to the chromedriver.exe file
    @param: liUsername: string of LI username
    @param: liPassword: string of LI password
    @return: driver: the Chrome Webdriver (can be passed into future function arguments)
'''
def setupDriver(driverPath, liUsername, liPassword):
    # Sets up Chrome Webdriver and navigates to LinkedIn
    driver = webdriver.Chrome(driverPath)
    driver.get('https://www.linkedin.com/')
    sleep(2.0)

    # Signs in with given credentials and returns the driver
    driver.find_element_by_xpath('//a[text()="Sign in"]').click()
    sleep(2.0)
    username_input = driver.find_element_by_name('session_key')
    username_input.send_keys(liUsername)
    password_input = driver.find_element_by_name('session_password')
    password_input.send_keys(liPassword)
    sleep(2.0)
    driver.find_element_by_xpath('//button[text()="Sign in"]').click()
    return driver

'''
Method to add LI information for a company into the company_data dictionary with a new company object
    @param: entry: a pandas series extracted from a single row in the dataframe from loadBacktestData
    @return: None
This method updates the company_data dictionary and returns nothing
'''
def extractLIInfo(entry):
    # Adds a new company entry to the company_data dictionary and populates fields
    company_ = Company(entry['Organization Name'])
    company_.description = entry['Description']
    company_.industries = [i.strip() for i in entry['Industries'].split(',')]
    company_.website = entry['Website']
    company_.lastStage = entry['Last Funding Type']
    # Edge case where the LinkedIn link does not end in '/'
    if entry['LinkedIn'][-1] != '/':
        entry['LinkedIn'] = entry['LinkedIn'] + '/'
    company_.linkedin = entry['LinkedIn']
    company_.location = entry['Headquarters Location']

    # Generates a list of founder names
    founderNames = [i.strip() for i in entry['Founders'].split(',')]
    # Navigates to the company's primary LinkedIn page [People Tab]
    try:
        driver.get(entry['LinkedIn'] + "people/")
        sleep(1.0)
        # For each founder in the list, the school name, degree, and major is extracted
        for founder in founderNames:
            name_input = driver.find_element_by_id('people-search-keywords')
            name_input.send_keys(founder)
            driver.find_element_by_id("people-search-keywords").send_keys(Keys.ENTER)
            sleep(1.0)
            try:
                driver.find_element_by_xpath('//a[@data-control-name = "people_profile_card_name_link"]').click()
                sleep(2.0)
                # Scrolls to the bottom of the webpage (if no scroll, error where the full webpage doens't load)
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight/2);")
                sleep(0.75)
                # Creates a founder object for the given founder
                founder_ = Founder(founder)

                ###########################################################
                # Extracts degree information (formatted as a list of items)
                schools = driver.find_elements_by_xpath('//div[@class="pv-entity__degree-info"]')
                for school in schools:
                    school_ = school.text.split('\n')
                    # The school is formatted as a list [School Name,'Degree Name',Degree Name,'Field of Study',FOS]
                    try:
                        educ_ = Education(school_[0])
                        try:
                            educ_.degree = school_[2]
                            educ_.field = school_[4]
                        except:
                            pass
                        # Appends the temporary education object to the founder
                        founder_.education.append(educ_)
                    except:
                        print("No schools")
                        pass

                ###############################################################
                # Extracts experience information (formatted as a list of items)
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight/3);")
                sleep(1.0)
                experiences = driver.find_elements_by_xpath('//a[@data-control-name="background_details_company"]')
                for exp in experiences:
                    exp_lst = exp.text.split('\n')
                    # The exp_ is formatted as [title, 'companyname', companyname, 'datesemployed', datesemployed, ..]
                    try:
                        if exp_lst[0] == 'Company Name':
                            exp_ = Experience(exp_lst[1])
                            founder_.experience.append(exp_)
                        else:
                            exp_ = Experience(exp_lst[2])
                            try:
                                exp_.title = exp_lst[0]
                                exp_.dates = exp_lst[4]
                                founder_.experience.append(exp_)
                            except:
                                founder_.experience.append(exp_)
                    except:
                        print("No experience")
                        pass
                # Appends the temporary founder object to the company
                company_.founders.append(founder_)
                # Re-navigates to company's LinkedIn page
                driver.get(entry['LinkedIn'] + "people/")
                sleep(1.0)
            except:
                founder_ = Founder(founder)
                company_.founders.append(founder_)
                print("{} not found for {}".format(company_.name, founder_.name))
                driver.get(entry['LinkedIn'] + "people/")
                sleep(1.0)
    except:
        print("LinkedIn page doesn't exist")
    # Adds the company to the company_data dictionary
    company_data[company_.name] = company_

    '''
Method to save the company data as a txt file (loadable as JSON)
    @param: data: company_data dictionary of Company objects
    @return: None
'''
def saveData(data, fileName):
    data_json = json.dumps(data, default=lambda x: x.__dict__)
    with open(fileName, 'w') as outfile:
        json.dump(data_json, outfile)

'''
Method to load company data into a dictionary (same structure as Company object)
    @param: dataFile: string path to saved txt file
    @return: dataDict: a dictionary with the same structure as a Company object
'''
def loadData(dataFile):
    with open(dataFile) as json_file:
        data = json.load(json_file)
    dataDict = json.loads(data)
    return dataDict

'''
Method to add LI information for a company into the company_data dictionary with a new company object
    @param: entry: a pandas series extracted from a single row in the dataframe from loadBacktestData
    @return: None
This method updates the company_data dictionary and returns nothing
'''
def scrapeLI(entry):
    # Adds a new company entry to the company_data dictionary and populates fields
    company_ = Company(entry['Organization Name'])
    company_.description = entry['Description']
    company_.industries = [i.strip() for i in entry['Industries'].split(',')]
    company_.website = entry['Website']
    company_.lastStage = entry['Last Funding Type']
    # Edge case where the LinkedIn link does not end in '/'
    if entry['LinkedIn'][-1] != '/':
        entry['LinkedIn'] = entry['LinkedIn'] + '/'
    company_.linkedin = entry['LinkedIn']
    company_.location = entry['Headquarters Location']

    # Generates a list of founder names
    founderNames = [i.strip() for i in entry['Founders'].split(',')]
    try:
        # For each founder in the list, the school name, degree, and major is extracted
        for founder in founderNames:
            # Finds the main search bar)
            search = driver.find_elements_by_xpath('//input[@class="search-global-typeahead__input always-show-placeholder"]')
            sleep(0.5)
            search[0].click()
            for i in range(50):
                search[0].send_keys(Keys.RIGHT)
            # Clears any existing search
            for i in range(80):
                search[0].send_keys(Keys.BACKSPACE)
            # Types in founder name + company name and searches
            search[0].send_keys(founder + " " + company_.name.split(" ")[0])
            search[0].send_keys(Keys.ENTER)
            sleep(2.0)
            try:
                a = driver.find_element_by_xpath('//a[@data-control-name="search_srp_result"]')
                if a:
                    a.click()
                    sleep(2.0)
                    # Scrolls to the bottom of the webpage (if no scroll, error where the full webpage doens't load)
                    driver.execute_script("window.scrollTo(0, document.body.scrollHeight/2);")
                    sleep(0.75)
                    # Creates a founder object for the given founder
                    founder_ = Founder(founder)
                   ###########################################################
#                  #Extracts data for connections
                    c = driver.find_elements_by_xpath('//ul[@class = "pv-top-card--list pv-top-card--list-bullet mt1"]/li[@class = "inline-block"]')
                    founder_.connections = (c[0].text)
                    ########
                    #Extract founder location
                    loc_ = driver.find_elements_by_xpath('//li[@class = "t-16 t-black t-normal inline-block"]')
                    founder_.location = (loc_[0].text)
                    ###########################################################
                    # Extracts degree information (formatted as a list of items)
                    schools = driver.find_elements_by_xpath('//div[@class="pv-entity__degree-info"]')
                    for school in schools:
                        school_ = school.text.split('\n')
                        # The school is formatted as a list [School Name,'Degree Name',Degree Name,'Field of Study',FOS]
                        try:
                            educ_ = Education(school_[0])
                            try:
                                educ_.degree = school_[2]
                                educ_.field = school_[4]
                            except:
                                pass
                            # Appends the temporary education object to the founder
                            founder_.education.append(educ_)
                        except:
                            print("No schools")
                            pass

                    ###############################################################
                    # Extracts experience information (formatted as a list of items)
                    driver.execute_script("window.scrollTo(0, document.body.scrollHeight/3);")
                    sleep(1.0)
                    experiences = driver.find_elements_by_xpath('//a[@data-control-name="background_details_company"]')
                    for exp in experiences:
                        exp_lst = exp.text.split('\n')
                        # The exp_ is formatted as [title, 'companyname', companyname, 'datesemployed', datesemployed, ..]
                        try:
                            if exp_lst[0] == 'Company Name':
                                exp_ = Experience(exp_lst[1])
                                founder_.experience.append(exp_)
                            else:
                                exp_ = Experience(exp_lst[2])
                                try:
                                    exp_.title = exp_lst[0]
                                    exp_.dates = exp_lst[4]
                                    founder_.experience.append(exp_)
                                except:
                                    founder_.experience.append(exp_)
                        except:
                            print("No experience")
                            pass
                    # Appends the temporary founder object to the company
                    company_.founders.append(founder_)
                    sleep(1.0)
                else:
                    founder_ = Founder(founder)
                    company_.founders.append(founder_)
                    print("{} not found for {}".format(company_.name, founder_.name))
                    sleep(1.0)
            except:
                print("{} not found for".format(company_.name, founder))
    except:
        print("Structural Error")
    # Adds the company to the company_data dictionary
    company_data[company_.name] = company_
