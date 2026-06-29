"""
git-proxy — GitLab API facade over CodeCommit.
Kiro Web connects to this as a self-managed GitLab instance.

Endpoints:
  GET  /api/v4/user                              → validate PAT
  GET  /api/v4/projects                          → list repos
  GET  /api/v4/projects/:id/repository/tree      → list files
  GET  /api/v4/projects/:id/repository/files/:path → read file
  POST /api/v4/projects/:id/repository/commits   → create commit
  GET  /api/v4/projects/:id/repository/branches  → list branches
  GET  /api/v4/projects/:id/merge_requests       → list MRs (stub)
  POST /api/v4/projects/:id/merge_requests       → create MR (stub)
  GET  /api/v4/projects/:id/issues               → list issues (stub)
"""
import json
import base64
import boto3
import os
import re

codecommit = boto3.client("codecommit", region_name="ap-south-1")

# PAT = any token we accept. For MVP, validate against a stored list.
VALID_TOKENS = set(os.environ.get("VALID_TOKENS", "").split(","))


def handler(event, context):
    try:
        return _handle(event, context)
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return resp(500, {"error": str(e)})


def _handle(event, context):
    path = event.get("rawPath", event.get("path", ""))
    method = event.get("requestContext", {}).get("http", {}).get("method",
             event.get("httpMethod", "GET"))
    headers = {k.lower(): v for k, v in (event.get("headers") or {}).items()}
    qs = event.get("queryStringParameters") or {}
    body = event.get("body", "")
    if event.get("isBase64Encoded") and body:
        # Don't decode here for binary endpoints (git); decode only for JSON endpoints
        if "git-upload-pack" not in path and "git-receive-pack" not in path:
            body = base64.b64decode(body).decode()

    print(f"REQUEST: {method} {path} qs={json.dumps(qs)}")
    if "/info/refs" in path or "/git-upload-pack" in path:
        print(f"GIT_HEADERS: {json.dumps({k:v for k,v in headers.items() if k != 'private-token'})}")

    # Auth — accept PRIVATE-TOKEN, Authorization: Bearer, or AuthToken
    token = headers.get("private-token", "")
    if not token:
        auth = headers.get("authorization", "")
        if auth.startswith("Bearer "):
            token = auth[7:]
    if not token:
        token = headers.get("authtoken", "")

    # Git protocol endpoints: allow if any auth header is present (gateway passes AuthToken)
    is_git_request = "/info/refs" in path or "/git-upload-pack" in path or "/git-receive-pack" in path
    if not is_git_request and token not in VALID_TOKENS:
        return resp(401, {"error": "Unauthorized"})
    if is_git_request and not token and not headers.get("authorization", ""):
        return resp(401, {"error": "Unauthorized"})

    # Route
    if path == "/api/v4/user":
        return handle_user()
    if path == "/api/v4/personal_access_tokens/self":
        return handle_pat_self(token)
    if path in ("/api/v4/version", "/api/v4/metadata"):
        return resp(200, {"version": "17.0.0", "revision": "codecommit-proxy"})
    if re.match(r"/api/v4/projects/?$", path):
        return handle_list_projects(qs)
    m = re.match(r"/api/v4/projects/([^/]+)$", path)
    if m and method == "GET" and "/repository" not in path:
        return handle_get_project(m.group(1))
    m = re.match(r"/api/v4/projects/(.+)/repository/tree", path)
    if m:
        return handle_tree(m.group(1), qs)
    m = re.match(r"/api/v4/projects/(.+)/repository/files/(.+)/raw", path)
    if m:
        return handle_file_raw(m.group(1), m.group(2), qs)
    m = re.match(r"/api/v4/projects/(.+)/repository/files/(.+)", path)
    if m and method == "GET":
        return handle_file(m.group(1), m.group(2), qs)
    m = re.match(r"/api/v4/projects/(.+)/repository/commits", path)
    if m and method == "POST":
        return handle_commit(m.group(1), json.loads(body))
    m = re.match(r"/api/v4/projects/(.+)/repository/branches", path)
    if m:
        return handle_branches(m.group(1), qs)
    m = re.match(r"/api/v4/projects/(.+)/merge_requests", path)
    if m:
        if method == "POST":
            return handle_create_mr(m.group(1), json.loads(body))
        return handle_list_mrs(m.group(1), qs)
    m = re.match(r"/api/v4/projects/(.+)/issues", path)
    if m:
        return resp(200, [])
    # Git smart HTTP protocol: /:namespace/:repo.git/info/refs and /git-upload-pack
    m = re.match(r"/(?:.+/)?([^/]+?)(?:\.git)?/info/refs", path)
    if m:
        return handle_git_info_refs(m.group(1), qs)
    m = re.match(r"/(?:.+/)?([^/]+?)(?:\.git)?/git-upload-pack", path)
    if m and method == "POST":
        print(f"UPLOAD_PACK: repo={m.group(1)} body_len={len(body) if body else 0} isBase64={event.get('isBase64Encoded')} raw_event_body_len={len(event.get('body',''))}")
        return handle_git_upload_pack(m.group(1), body, event, headers)
    m = re.match(r"/(?:.+/)?([^/]+?)(?:\.git)?/git-receive-pack", path)
    if m and method == "POST":
        print(f"RECEIVE_PACK: repo={m.group(1)}")
        return handle_git_receive_pack(m.group(1), body, event, headers)
    return resp(404, {"error": "Not found", "path": path})


def handle_user():
    return resp(200, {
        "id": 1,
        "username": "codecommit",
        "name": "CodeCommit User",
        "state": "active",
        "web_url": "https://git.next.skith.in",
    })


def handle_pat_self(token):
    return resp(200, {
        "id": 1,
        "name": "kiro-web",
        "active": True,
        "user_id": 1,
        "scopes": ["api"],
        "created_at": "2026-01-01T00:00:00.000Z",
        "expires_at": "2027-01-01",
    })


def handle_list_projects(qs):
    repos = codecommit.list_repositories()["repositories"]
    projects = []
    for i, r in enumerate(repos):
        projects.append(_project_obj(i + 1, r["repositoryName"]))
    return resp(200, projects)


def handle_get_project(project_id):
    repo = resolve_repo(project_id)
    try:
        meta = codecommit.get_repository(repositoryName=repo)["repositoryMetadata"]
    except Exception as e:
        return resp(404, {"error": str(e)})
    repos = codecommit.list_repositories()["repositories"]
    idx = next((i for i, r in enumerate(repos) if r["repositoryName"] == repo), 0)
    return resp(200, _project_obj(idx + 1, repo, meta.get("repositoryDescription", "")))


def _project_obj(pid, name, description=""):
    return {
        "id": pid,
        "name": name,
        "path": name,
        "path_with_namespace": name,
        "namespace": {"id": 1, "name": "codecommit", "path": "codecommit", "kind": "group"},
        "default_branch": "main",
        "visibility": "private",
        "description": description,
        "web_url": f"https://git.next.skith.in/{name}",
        "ssh_url_to_repo": "",
        "http_url_to_repo": f"https://git.next.skith.in/{name}.git",
        "readme_url": f"https://git.next.skith.in/{name}/-/blob/main/README.md",
        "permissions": {"project_access": {"access_level": 40}, "group_access": None},
    }


def handle_tree(project_id, qs):
    repo = resolve_repo(project_id)
    ref = qs.get("ref", "main")
    path = qs.get("path", "")
    try:
        r = codecommit.get_folder(repositoryName=repo, folderPath=path or "/", commitSpecifier=ref)
    except Exception as e:
        return resp(404, {"error": str(e)})
    items = []
    for f in r.get("files", []):
        items.append({"name": f["relativePath"], "path": f["absolutePath"].lstrip("/"),
                      "type": "blob", "mode": "100644"})
    for d in r.get("subFolders", []):
        items.append({"name": d["relativePath"], "path": d["absolutePath"].lstrip("/"),
                      "type": "tree", "mode": "040000"})
    return resp(200, items)


def handle_file(project_id, file_path, qs):
    repo = resolve_repo(project_id)
    ref = qs.get("ref", "main")
    file_path = file_path.replace("%2F", "/").replace("%2f", "/")
    try:
        r = codecommit.get_file(repositoryName=repo, filePath=file_path, commitSpecifier=ref)
    except Exception as e:
        return resp(404, {"error": str(e)})
    content = base64.b64encode(r["fileContent"]).decode()
    return resp(200, {
        "file_name": file_path.split("/")[-1],
        "file_path": file_path,
        "size": r["fileSize"],
        "encoding": "base64",
        "content": content,
        "ref": ref,
        "blob_id": r["blobId"],
        "commit_id": r["commitId"],
    })


def handle_file_raw(project_id, file_path, qs):
    repo = resolve_repo(project_id)
    ref = qs.get("ref", "main")
    file_path = file_path.replace("%2F", "/").replace("%2f", "/")
    try:
        r = codecommit.get_file(repositoryName=repo, filePath=file_path, commitSpecifier=ref)
    except Exception as e:
        return resp(404, {"error": str(e)})
    return {
        "statusCode": 200,
        "headers": {"content-type": "application/octet-stream"},
        "body": base64.b64encode(r["fileContent"]).decode(),
        "isBase64Encoded": True,
    }


def handle_commit(project_id, data):
    repo = resolve_repo(project_id)
    branch = data.get("branch", "main")
    message = data.get("commit_message", "commit via kiro")
    actions = data.get("actions", [])
    put_files = []
    delete_files = []
    for a in actions:
        if a["action"] in ("create", "update"):
            content = a.get("content", "")
            if a.get("encoding") == "base64":
                content = base64.b64decode(content)
            else:
                content = content.encode()
            put_files.append({"filePath": a["file_path"], "fileContent": content})
        elif a["action"] == "delete":
            delete_files.append({"filePath": a["file_path"]})
    try:
        r = codecommit.create_commit(
            repositoryName=repo,
            branchName=branch,
            parentCommitId=get_head(repo, branch),
            putFiles=put_files,
            deleteFiles=delete_files,
            commitMessage=message,
            authorName=data.get("author_name", "Kiro"),
            authorEmail=data.get("author_email", "kiro@kiro.dev"),
        )
    except Exception as e:
        return resp(400, {"error": str(e)})
    return resp(201, {
        "id": r["commitId"],
        "short_id": r["commitId"][:8],
        "message": message,
    })


def handle_branches(project_id, qs):
    repo = resolve_repo(project_id)
    try:
        r = codecommit.list_branches(repositoryName=repo)
    except Exception as e:
        return resp(404, {"error": str(e)})
    branches = []
    for b in r.get("branches", []):
        branches.append({"name": b, "default": b == "main", "web_url": f"https://ap-south-1.console.aws.amazon.com/codesuite/codecommit/repositories/{repo}/browse/refs/heads/{b}"})
    return resp(200, branches)


def handle_list_mrs(project_id, qs):
    repo = resolve_repo(project_id)
    try:
        r = codecommit.list_pull_requests(repositoryName=repo,
            pullRequestStatus=qs.get("state", "OPEN").upper())
    except Exception:
        return resp(200, [])
    mrs = []
    for pr_id in r.get("pullRequestIds", [])[:20]:
        pr = codecommit.get_pull_request(pullRequestId=pr_id)["pullRequest"]
        mrs.append({
            "iid": int(pr_id),
            "title": pr["title"],
            "state": "opened" if pr["pullRequestStatus"] == "OPEN" else "merged",
            "source_branch": pr["pullRequestTargets"][0]["sourceReference"].split("/")[-1],
            "target_branch": pr["pullRequestTargets"][0]["destinationReference"].split("/")[-1],
            "web_url": f"https://ap-south-1.console.aws.amazon.com/codesuite/codecommit/repositories/{repo}/pull-requests/{pr_id}",
        })
    return resp(200, mrs)


def handle_create_mr(project_id, data):
    repo = resolve_repo(project_id)
    try:
        r = codecommit.create_pull_request(
            title=data.get("title", "MR from Kiro"),
            targets=[{
                "repositoryName": repo,
                "sourceReference": data.get("source_branch", "main"),
                "destinationReference": data.get("target_branch", "main"),
            }],
            description=data.get("description", ""),
        )
    except Exception as e:
        return resp(400, {"error": str(e)})
    pr = r["pullRequest"]
    return resp(201, {
        "iid": int(pr["pullRequestId"]),
        "title": pr["title"],
        "state": "opened",
        "web_url": f"https://ap-south-1.console.aws.amazon.com/codesuite/codecommit/repositories/{repo}/pull-requests/{pr['pullRequestId']}",
    })


# --- Helpers ---

def handle_git_info_refs(repo_name, qs):
    """Proxy git smart HTTP info/refs to CodeCommit."""
    import urllib.request
    service = qs.get("service", "git-upload-pack")
    url = _codecommit_git_url(repo_name) + f"/info/refs?service={service}"
    try:
        req = urllib.request.Request(url)
        _sign_codecommit_request(req, repo_name)
        with urllib.request.urlopen(req, timeout=25) as r:
            body = r.read()
            return {
                "statusCode": 200,
                "headers": {
                    "content-type": f"application/x-{service}-advertisement",
                    "cache-control": "no-cache",
                },
                "body": base64.b64encode(body).decode(),
                "isBase64Encoded": True,
            }
    except Exception as e:
        print(f"git info/refs error: {e}")
        return resp(500, {"error": str(e)})


def handle_git_upload_pack(repo_name, body, event, headers):
    """Proxy git-upload-pack POST to CodeCommit."""
    import urllib.request
    url = _codecommit_git_url(repo_name) + "/git-upload-pack"
    raw_body = body
    if event.get("isBase64Encoded") and raw_body:
        raw_body += "=" * (-len(raw_body) % 4)  # fix padding
        raw_body = base64.b64decode(raw_body)
    elif isinstance(raw_body, str):
        raw_body = raw_body.encode("latin-1")  # preserve binary bytes
    print(f"UPLOAD_PACK_BODY: {len(raw_body)} bytes, first 20 hex: {raw_body[:20].hex()}")
    try:
        req = urllib.request.Request(url, data=raw_body, method="POST")
        req.add_header("Content-Type", "application/x-git-upload-pack-request")
        _sign_codecommit_request(req, repo_name)
        with urllib.request.urlopen(req, timeout=55) as r:
            resp_body = r.read()
            print(f"UPLOAD_PACK_RESP: {len(resp_body)} bytes, status={r.status}")
            return {
                "statusCode": 200,
                "headers": {"content-type": "application/x-git-upload-pack-result"},
                "body": base64.b64encode(resp_body).decode(),
                "isBase64Encoded": True,
            }
    except urllib.request.HTTPError as e:
        err_body = e.read().decode(errors="replace")
        print(f"git-upload-pack HTTPError: {e.code} {e.reason} body={err_body[:200]}")
        return resp(e.code, {"error": f"{e.code} {e.reason}", "detail": err_body[:200]})
    except Exception as e:
        print(f"git-upload-pack error: {e}")
        return resp(500, {"error": str(e)})


def handle_git_receive_pack(repo_name, body, event, headers):
    """Proxy git-receive-pack POST (push) to CodeCommit."""
    import urllib.request
    url = _codecommit_git_url(repo_name) + "/git-receive-pack"
    raw_body = body
    if event.get("isBase64Encoded") and raw_body:
        raw_body += "=" * (-len(raw_body) % 4)
        raw_body = base64.b64decode(raw_body)
    elif isinstance(raw_body, str):
        raw_body = raw_body.encode("latin-1")
    print(f"RECEIVE_PACK_BODY: {len(raw_body)} bytes")
    try:
        req = urllib.request.Request(url, data=raw_body, method="POST")
        req.add_header("Content-Type", "application/x-git-receive-pack-request")
        _sign_codecommit_request(req, repo_name)
        with urllib.request.urlopen(req, timeout=55) as r:
            resp_body = r.read()
            print(f"RECEIVE_PACK_RESP: {len(resp_body)} bytes, status={r.status}")
            return {
                "statusCode": 200,
                "headers": {"content-type": "application/x-git-receive-pack-result"},
                "body": base64.b64encode(resp_body).decode(),
                "isBase64Encoded": True,
            }
    except urllib.request.HTTPError as e:
        err_body = e.read().decode(errors="replace")
        print(f"git-receive-pack HTTPError: {e.code} {e.reason} body={err_body[:200]}")
        return resp(e.code, {"error": f"{e.code} {e.reason}", "detail": err_body[:200]})
    except Exception as e:
        print(f"git-receive-pack error: {e}")
        return resp(500, {"error": str(e)})


def _codecommit_git_url(repo_name):
    return f"https://git-codecommit.ap-south-1.amazonaws.com/v1/repos/{repo_name}"


def _sign_codecommit_request(req, repo_name):
    """Sign request using CodeCommit GRC-style SigV4 basic auth."""
    import datetime
    import botocore.auth
    import botocore.awsrequest
    import botocore.credentials

    session = boto3.Session()
    credentials = session.get_credentials().get_frozen_credentials()
    region = "ap-south-1"
    hostname = f"git-codecommit.{region}.amazonaws.com"
    path = f"/v1/repos/{repo_name}"

    # GRC signing
    aws_request = botocore.awsrequest.AWSRequest(method="GIT", url=f"https://{hostname}{path}")
    aws_request.context["timestamp"] = datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%S")
    signer = botocore.auth.SigV4Auth(credentials, "codecommit", region)
    canonical_request = f"GIT\n{path}\n\nhost:{hostname}\n\nhost\n"
    string_to_sign = signer.string_to_sign(aws_request, canonical_request)
    signature = signer.signature(string_to_sign, aws_request)
    password = f"{aws_request.context['timestamp']}Z{signature}"

    # Basic auth header
    username = credentials.access_key
    if credentials.token:
        username = f"{credentials.access_key}%{credentials.token}"
    import base64 as b64
    auth_str = b64.b64encode(f"{username}:{password}".encode()).decode()
    req.add_header("Authorization", f"Basic {auth_str}")


def resolve_repo(project_id):
    """Resolve project ID (could be numeric index, name, or namespace/name)."""
    project_id = project_id.replace("%2F", "/").replace("%2f", "/")
    if project_id.isdigit():
        repos = codecommit.list_repositories()["repositories"]
        idx = int(project_id) - 1
        if 0 <= idx < len(repos):
            return repos[idx]["repositoryName"]
    # If namespace/name format, take the last segment (CodeCommit has flat namespace)
    if "/" in project_id:
        project_id = project_id.split("/")[-1]
    return project_id


def get_head(repo, branch):
    r = codecommit.get_branch(repositoryName=repo, branchName=branch)
    return r["branch"]["commitId"]


def resp(status, body):
    return {
        "statusCode": status,
        "headers": {"content-type": "application/json"},
        "body": json.dumps(body),
    }
