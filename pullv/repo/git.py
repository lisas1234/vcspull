from .base import BaseRepo
import logging
from ..util import _run
import os
logger = logging.getLogger(__name__)

class GitRepo(BaseRepo):
    schemes = ('git')

    def __init__(self, arguments, *args, **kwargs):

        BaseRepo.__init__(self, arguments, *args, **kwargs)

    def get_revision(self):
        current_rev = _run(
            ['git', 'rev-parse', 'HEAD'],
            cwd=self['path']
        )

        return current_rev['stdout']

    def obtain(self):
        self.check_destination()

        url, rev = self.get_url_rev()
        proc = _run(
            ['git', 'clone', '-q', url, self['path']],
            env=os.environ.copy(), cwd=self['path']
        )

    def update_repo(self):
        self.check_destination()
        if os.path.isdir(os.path.join(self['path'], '.git')):

            logging.info('fetching...', extra=self.prefixed_dict)
            proc = _run([
                'git', 'fetch'
            ], cwd=self['path'])
            logging.info('fetched: {0}'.format(proc['stdout']), extra=self.prefixed_dict
                         )

            logging.info('pulling...', extra=self.prefixed_dict)
            proc = _run([
                'git', 'pull'
            ], cwd=self['path'])
            logging.info('pulled: {0}'.format(proc['stdout']), extra=self.prefixed_dict)
        else:
            self.obtain()
            self.update_repo()

