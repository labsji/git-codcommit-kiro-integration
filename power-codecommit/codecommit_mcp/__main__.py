"""
CodeCommit MCP Server — tools for Kiro to interact with AWS CodeCommit.

Run: python3 -m codecommit_mcp
"""
import json
import sys
import base64
import boto3

REGION = __import__("os").environ.get("AWS_REGION", "ap-south-1")
cc = boto3.client("codecommit", region_name=REGION)


def handle_request(request):
    method = request.get("method")
    params = request.get("params", {})

    if method == "initialize":
        return {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}},
                "serverInfo": {"name": "codecommit-mcp", "version": "1.0.0"}}

    if method == "tools/list":
        return {"tools": TOOLS}

    if method == "tools/call":
        name = params.get("name")
        args = params.get("arguments", {})
        result = call_tool(name, args)
        return {"content": [{"type": "text", "text": result}]}

    return {"error": {"code": -32601, "message": f"Unknown method: {method}"}}


def call_tool(name, args):
    try:
        if name == "list_repos":
            repos = cc.list_repositories()["repositories"]
            return "\n".join(r["repositoryName"] for r in repos)

        elif name == "list_files":
            repo = args["repo"]
            path = args.get("path", "/")
            ref = args.get("ref", "main")
            r = cc.get_folder(repositoryName=repo, folderPath=path, commitSpecifier=ref)
            lines = []
            for d in r.get("subFolders", []):
                lines.append(f"📁 {d['relativePath']}/")
            for f in r.get("files", []):
                lines.append(f"📄 {f['relativePath']}")
            return "\n".join(lines) or "(empty)"

        elif name == "get_file":
            repo = args["repo"]
            path = args["path"]
            ref = args.get("ref", "main")
            r = cc.get_file(repositoryName=repo, filePath=path, commitSpecifier=ref)
            return r["fileContent"].decode("utf-8", errors="replace")

        elif name == "create_commit":
            repo = args["repo"]
            branch = args.get("branch", "main")
            message = args["message"]
            files = args["files"]  # list of {path, content} or {path, delete: true}
            head = cc.get_branch(repositoryName=repo, branchName=branch)["branch"]["commitId"]
            put_files = []
            delete_files = []
            for f in files:
                if f.get("delete"):
                    delete_files.append({"filePath": f["path"]})
                else:
                    put_files.append({"filePath": f["path"], "fileContent": f["content"].encode()})
            r = cc.create_commit(repositoryName=repo, branchName=branch,
                                 parentCommitId=head, putFiles=put_files,
                                 deleteFiles=delete_files, commitMessage=message)
            return f"Committed: {r['commitId'][:8]} on {branch}"

        elif name == "create_branch":
            repo = args["repo"]
            branch = args["branch"]
            from_ref = args.get("from_ref", "main")
            head = cc.get_branch(repositoryName=repo, branchName=from_ref)["branch"]["commitId"]
            cc.create_branch(repositoryName=repo, branchName=branch, commitId=head)
            return f"Branch '{branch}' created from {from_ref}"

        elif name == "list_branches":
            repo = args["repo"]
            r = cc.list_branches(repositoryName=repo)
            return "\n".join(r["branches"])

        elif name == "create_pr":
            repo = args["repo"]
            title = args["title"]
            source = args["source_branch"]
            target = args.get("target_branch", "main")
            desc = args.get("description", "")
            r = cc.create_pull_request(title=title, description=desc, targets=[{
                "repositoryName": repo,
                "sourceReference": source,
                "destinationReference": target,
            }])
            return f"PR #{r['pullRequest']['pullRequestId']}: {title}"

        elif name == "list_prs":
            repo = args["repo"]
            state = args.get("state", "OPEN")
            r = cc.list_pull_requests(repositoryName=repo, pullRequestStatus=state)
            if not r["pullRequestIds"]:
                return "No pull requests found."
            lines = []
            for pr_id in r["pullRequestIds"][:10]:
                pr = cc.get_pull_request(pullRequestId=pr_id)["pullRequest"]
                lines.append(f"#{pr_id}: {pr['title']} ({pr['pullRequestStatus']})")
            return "\n".join(lines)

        else:
            return f"Unknown tool: {name}"
    except Exception as e:
        return f"Error: {e}"


TOOLS = [
    {"name": "list_repos", "description": "List all CodeCommit repositories",
     "inputSchema": {"type": "object", "properties": {}}},
    {"name": "list_files", "description": "List files and folders in a repository path",
     "inputSchema": {"type": "object", "properties": {
         "repo": {"type": "string", "description": "Repository name"},
         "path": {"type": "string", "description": "Folder path (default: /)", "default": "/"},
         "ref": {"type": "string", "description": "Branch or commit ref", "default": "main"},
     }, "required": ["repo"]}},
    {"name": "get_file", "description": "Read file content from a repository",
     "inputSchema": {"type": "object", "properties": {
         "repo": {"type": "string", "description": "Repository name"},
         "path": {"type": "string", "description": "File path"},
         "ref": {"type": "string", "description": "Branch or commit ref", "default": "main"},
     }, "required": ["repo", "path"]}},
    {"name": "create_commit", "description": "Create a commit with file changes",
     "inputSchema": {"type": "object", "properties": {
         "repo": {"type": "string", "description": "Repository name"},
         "branch": {"type": "string", "description": "Branch to commit to", "default": "main"},
         "message": {"type": "string", "description": "Commit message"},
         "files": {"type": "array", "description": "Files to create/update/delete",
                   "items": {"type": "object", "properties": {
                       "path": {"type": "string"}, "content": {"type": "string"},
                       "delete": {"type": "boolean"}}}},
     }, "required": ["repo", "message", "files"]}},
    {"name": "create_branch", "description": "Create a new branch",
     "inputSchema": {"type": "object", "properties": {
         "repo": {"type": "string", "description": "Repository name"},
         "branch": {"type": "string", "description": "New branch name"},
         "from_ref": {"type": "string", "description": "Base branch", "default": "main"},
     }, "required": ["repo", "branch"]}},
    {"name": "list_branches", "description": "List all branches in a repository",
     "inputSchema": {"type": "object", "properties": {
         "repo": {"type": "string", "description": "Repository name"},
     }, "required": ["repo"]}},
    {"name": "create_pr", "description": "Create a pull request",
     "inputSchema": {"type": "object", "properties": {
         "repo": {"type": "string", "description": "Repository name"},
         "title": {"type": "string", "description": "PR title"},
         "source_branch": {"type": "string", "description": "Source branch"},
         "target_branch": {"type": "string", "description": "Target branch", "default": "main"},
         "description": {"type": "string", "description": "PR description", "default": ""},
     }, "required": ["repo", "title", "source_branch"]}},
    {"name": "list_prs", "description": "List pull requests",
     "inputSchema": {"type": "object", "properties": {
         "repo": {"type": "string", "description": "Repository name"},
         "state": {"type": "string", "description": "OPEN or CLOSED", "default": "OPEN"},
     }, "required": ["repo"]}},
]


# --- STDIO JSON-RPC transport ---
def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        request = json.loads(line)
        response = handle_request(request)
        response["jsonrpc"] = "2.0"
        response["id"] = request.get("id")
        sys.stdout.write(json.dumps(response) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
