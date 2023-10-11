import os
import requests
import json
from dotenv import load_dotenv

import openai
import html


def remove_github_header(text):
  lines = text.split("\n")
  for i, line in enumerate(lines):
    if line.startswith("From ") and lines[i + 1].startswith("Date: "):
      return "\n".join(lines[i + 2:])
  return text


# WHITELIST = ["Narteno"] # move this to github actions (probably some 'uses' I don't know about
def get_pr_url(url):
  # Split the URL by '/' to extract the owner and repo name
  url_parts = url.split("/")
  owner = url_parts[3]
  repo = url_parts[4]
  pr_number = url_parts[-1]

  # Construct the API URL to retrieve pull request data
  api_url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}"

  return api_url


def split_patch_file_content(patch_text):
  files = []
  current_file = []
  lines = patch_text.split("\n")
  for i, line in enumerate(lines):
    if line.startswith("diff --git"):
      if current_file:
        files.append(("\n".join(current_file), i))
      current_file = [line]
    else:
      current_file.append(line)
  if current_file:
    files.append(("\n".join(current_file), i))
  return files


def get_pr_files(owner, repo, pr_number, access_token):
  # Construct the API URL to retrieve pull request data
  api_url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}/files"

  # Retrieve the pull request data
  response = requests.get(
      api_url, headers={"Authorization": f"token {access_token}"})
  response.raise_for_status()

  return response.json()


def extract_last_changed_line_number(diff):
  lines = diff.split('\n')
  start_line = None
  for line in lines:
    if line.startswith('@@'):
      line_info = line.split()[2]  # Extract the part after "@@"
      # Split the line range into start and num_lines
      start_line, num_lines = line_info.split(',')
      start_line = int(start_line)
      num_lines = int(num_lines)
      end_line = start_line + num_lines - 1  # Compute the last line number
  return end_line


def extract_first_changed_line_number(diff):
  lines = diff.split('\n')
  for line in lines:
    if line.startswith('@@'):
      line_info = line.split()[2]  # Extract the part after "@@"
      # Split the line range into start and num_lines
      start_line, num_lines = line_info.split(',')
      start_line = int(start_line)
      num_lines = int(num_lines)
      end_line = start_line + num_lines - 1  # Compute the last line number
      return end_line
  return None


def get_review_v2():
  github_env = os.getenv("GITHUB_ENV")

  with open(github_env, "r") as f:
    variables = dict([line.split("=") for line in f.read().splitlines()])

  ACCESS_TOKEN = variables["GITHUB_TOKEN"]

  pr_link = variables["LINK"]
  openai.api_key = variables["OPENAI_API_KEY"]

  # get pr owner, repo, pr_number
  owner = pr_link.split("/")[-4]
  repo = pr_link.split("/")[-3]
  pr_number = pr_link.split("/")[-1]

  pr_files = get_pr_files(owner, repo, pr_number, ACCESS_TOKEN)

  ignore_file_ext = ["md", "txt", "json", "snap"]

  for pr_file in pr_files:
    # get the file patch
    diff_hunk = pr_file["patch"]
    filename = pr_file["filename"]

    # ignore files with certain extensions
    if filename.split(".")[-1] in ignore_file_ext:
      continue

    commit_id = pr_file["contents_url"].split("?")[1].split("=")[1]

    print(diff_hunk)
    line_to_comment = extract_last_changed_line_number(diff_hunk)

    try:
      review = get_review_from_openai(diff_hunk)

      review_comment = {
          "body": review,
          "path": filename,
          "line": line_to_comment,
          "commit_id": commit_id
        }

      # Post the review comment to GitHub using the GitHub API
      url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}/comments"

      if review.strip() != "LGTM":
        response = requests.post(
          url, headers={"Authorization": f"token {ACCESS_TOKEN}"}, json=review_comment)
  
        if response.status_code != 201:
          print(
            f"Error posting review comment for {filename}: {response.json()}")
    except Exception as e:
      print(e)
      continue


def get_review_from_openai(patch):
  # model = "text-ada-001"
  model = "gpt-3.5-turbo"
  patch_tokens = 1000  # need to calcualte tokens

  question = "Code Review Request for Bugs, Issues, or Standard Violations, lint errors, Dont check for unused. Say LGTM if no issues found. \n"
  messages =  [{"role": "user",  "content": question + patch}]

  response = openai.ChatCompletion.create(
      model=model,
      messages=messages,
  )

  review = response["choices"][0]["message"]["content"]

  return review


def get_review():
  github_env = os.getenv("GITHUB_ENV")

  with open(github_env, "r") as f:
    variables = dict([line.split("=") for line in f.read().splitlines()])

  ACCESS_TOKEN = variables["GITHUB_TOKEN"]

  pr_link = variables["LINK"]
  openai.api_key = variables["OPENAI_API_KEY"]

  request_link = get_pr_url(pr_link)

  headers = {
      "Authorization": f"Bearer {ACCESS_TOKEN}",
      "Accept": "application/vnd.github.VERSION.diff",
  }

  patch = requests.get(request_link, headers=headers).text

  # model = "text-ada-001"
  model = "gpt-3.5-turbo"
  patch_tokens = 1000  # need to calcualte tokens

  patch_contents = split_patch_file_content(patch)

  for file_patch, line_number in patch_contents:
    question = "Code Review Request for Bugs, Issues, or Standard Violations, lint errors, Dont check for unused. Say LGTM if no issues found.. \n"
    prompt = question + file_patch

    response = openai.Completion.create(
        engine=model,
        prompt=prompt,
        temperature=0.9,
        # TODO: need to find a dynamic way of setting this according to the prompt
        max_tokens=patch_tokens,
        top_p=1.0,
        frequency_penalty=0.0,
        presence_penalty=0.0,
    )
    review = response["choices"][0]["text"]

    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/x-www-form-urlencoded",
    }

    data = {"body": review, "line": line_number}
    data = json.dumps(data)

    OWNER = pr_link.split("/")[-4]
    REPO = pr_link.split("/")[-3]
    PR_NUMBER = pr_link.split("/")[-1]

    if review.strip() != "LGTM":
      response = requests.post(
          f"https://api.github.com/repos/{OWNER}/{REPO}/issues/{PR_NUMBER}/comments",
          headers=headers,
          data=data,
      )
      print(response.json())


if __name__ == "__main__":
  load_dotenv()
  get_review_v2()
