#!/usr/bin/env python3
"""
Test script to verify Jenkins fetch functionality and error handling
"""

from jenkins.jenkins_fetcher import read_credentials, fetch_job_status
import configparser

def test_jenkins_fetch():
    # Read configuration
    config_urls = configparser.ConfigParser()
    config_urls.read("jenkins/job_config.ini")
    
    config_groups = configparser.ConfigParser() 
    config_groups.read("jenkins/groups.ini")
    
    # Read credentials
    username, token = read_credentials("jenkins/credentials.ini")
    
    print(f"Testing with username: {username}")
    print("="*50)
    
    # Test a few jobs
    test_jobs = [
        {"name": "USM_7_6_MAIN", "url": config_urls["URLS"].get("USM_7_6_MAIN")},
        {"name": "USM_7_7_MAIN", "url": config_urls["URLS"].get("USM_7_7_MAIN")},
        {"name": "USM_7_88_MIAN", "url": config_urls["URLS"].get("USM_7_88_MIAN")},
    ]
    
    for job in test_jobs:
        if job["url"]:
            print(f"\nTesting job: {job['name']}")
            print(f"URL: {job['url']}")
            
            result = fetch_job_status(job, username, token)
            
            if "error" in result:
                print(f"❌ Error: {result['error']}")
            else:
                print(f"✅ Success: Build #{result.get('number', 'N/A')} - {result.get('result', 'N/A')}")
        else:
            print(f"\n❌ Job {job['name']} has no URL configured")

if __name__ == "__main__":
    test_jenkins_fetch()