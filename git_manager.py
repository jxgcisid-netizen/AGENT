import os
import subprocess
import tempfile

class GitManager:
    def __init__(self, repo_path):
        self.repo_path = repo_path
        self._ensure_git()
    
    def _ensure_git(self):
        if not os.path.exists(os.path.join(self.repo_path, ".git")):
            subprocess.run(["git", "init"], cwd=self.repo_path, check=True)
            remote = os.getenv("GIT_REMOTE_URL")
            if remote:
                subprocess.run(["git", "remote", "add", "origin", remote], cwd=self.repo_path)
    
    def apply_patch(self, patch_text, commit_message="Self-modify"):
        try:
            with tempfile.NamedTemporaryFile(mode="w", suffix=".diff", delete=False) as f:
                f.write(patch_text)
                patch_file = f.name
            subprocess.run(["git", "apply", patch_file], cwd=self.repo_path, check=True)
            subprocess.run(["git", "add", "."], cwd=self.repo_path, check=True)
            subprocess.run(["git", "commit", "-m", commit_message], cwd=self.repo_path, check=True)
            subprocess.run(["git", "push", "origin", "main"], cwd=self.repo_path, check=True)
            return True
        except subprocess.CalledProcessError as e:
            print(f"Git error: {e}")
            return False
        finally:
            os.unlink(patch_file)
