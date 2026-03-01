import configparser


def load_catalog(job_config_path, groups_config_path):
    config_urls = configparser.ConfigParser()
    config_urls.read(job_config_path)

    config_groups = configparser.ConfigParser()
    config_groups.read(groups_config_path)

    return config_urls, config_groups


def _make_job_entry(config_urls, job_name):
    url = config_urls["URLS"].get(job_name)
    if not url:
        return None

    display_name = job_name
    if job_name in config_urls:
        display_name = config_urls[job_name].get("display_name", job_name)

    return {
        "name": job_name,
        "url": url,
        "display_name": display_name,
    }


def resolve_jobs(query_text, config_urls, config_groups):
    matched_jobs = []

    if not query_text:
        for section in config_groups.sections():
            job_names = [j.strip() for j in config_groups[section]["jobs"].split(",")]
            for name in job_names:
                entry = _make_job_entry(config_urls, name)
                if entry:
                    matched_jobs.append(entry)
        return matched_jobs

    if query_text.upper() in config_groups:
        job_names = [j.strip() for j in config_groups[query_text.upper()]["jobs"].split(",")]
        for name in job_names:
            entry = _make_job_entry(config_urls, name)
            if entry:
                matched_jobs.append(entry)
        return matched_jobs

    for section in config_urls.sections():
        if section == "URLS":
            continue
        job_name = section
        aliases = config_urls[section].get("alias", "").lower().split(",")
        all_keywords = [job_name.lower()] + [a.strip() for a in aliases if a.strip()]

        for keyword in all_keywords:
            if query_text == keyword:
                entry = _make_job_entry(config_urls, job_name)
                if entry:
                    matched_jobs.append(entry)
                break

    return matched_jobs
