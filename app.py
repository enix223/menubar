import rumps
from rumps import MenuItem
import os
import subprocess

from safety.safety import check
from safety.util import read_requirements, Package as SafetyPackage, RequirementFile as SafetyRequirementFile

class ICONS:
    GRAY = 'icons/gray.png'
    GREEN = 'icons/green.png'
    RED = 'icons/red.png'


class RequirementFile(object):

    def __init__(self, project, path, requirements):
        self.project = project
        self.path = path

        self.menu_item = MenuItem(
            self.path,
            key=path,
            callback=self.clicked,
            icon=ICONS.GRAY,
        )

        self.requirements = requirements

    def clicked(self, sender):
        # todo: is there a way to open natively?
        subprocess.call(['open', self.path])

    def check(self):
        # todo: remove sleep here. This is to show that the main loop hangs when updating the UI
        import time
        time.sleep(2)
        vulns = check(self.requirements)
        if vulns:
            self.menu_item.icon = ICONS.RED
        else:
            self.menu_item.icon = ICONS.GREEN
        return vulns


class Project(object):

    def __init__(self, app, path):
        self.app = app
        self.path = path
        self.name = path.split("/")[-1]
        self.insecure = None

        self.menu_item = MenuItem(
            self.path,
            callback=self.clicked,
            key=self.path,
            icon=ICONS.GRAY,
        )

        self.requirement_files = None

    @property
    def is_valid(self):
        return self.requirement_files is not None and self.requirement_files

    @property
    def needs_check(self):
        return self.insecure is None

    def find_requirement_files(self):
        def is_likely_a_requirement(path):
            if "req" in path:
                if path.endswith(".txt") or path.endswith(".pip"):
                    return True
            return False

        def parse(file_name):
            reqs = []
            try:
                with open(file_name) as fh:
                    for item in read_requirements(fh):
                        if isinstance(item, SafetyPackage):
                            reqs.append(item)
                        elif isinstance(item, SafetyRequirementFile):
                            for other_file in parse(item.path):
                                yield other_file
                    if reqs:
                        yield RequirementFile(
                            project=self,
                            requirements=reqs,
                            path=file_name
                        )
            except FileNotFoundError:
                pass

        for item in os.listdir(self.path):
            full_path = os.path.join(self.path, item)
            if os.path.isdir(full_path):
                for item_deep in os.listdir(full_path):
                    full_path_deep = os.path.join(full_path, item_deep)
                    if os.path.isfile(full_path_deep) and is_likely_a_requirement(full_path_deep):
                        for req_file in parse(full_path_deep):
                            yield req_file
            elif os.path.isfile(full_path) and is_likely_a_requirement(full_path):
                for req_file in parse(full_path):
                    yield req_file

    def check(self):
        if self.requirement_files is None:
            self.requirement_files = list(self.find_requirement_files())

        insecure = False
        for req in self.requirement_files:
            vulns = req.check()
            if vulns:
                insecure = True
        self.insecure = insecure
        if insecure:
            self.menu_item.icon = ICONS.RED
        else:
            self.menu_item.icon = ICONS.GREEN

    def add(self):
        # todo: when adding the menu item, add it before the seperator, ideally ordered by path
        self.menu_item.update(
            [r.menu_item for r in self.requirement_files]
        )
        self.app.menu.update(self.menu_item)

    def clicked(self, sender):
        # todo: is there a way to open natively?
        subprocess.call(['open', self.path])

    def __eq__(self, other):
        if isinstance(other, Project):
            return self.path == other.path
        return super(Project, self).__eq__(other)

    def __ne__(self, other):
        return not self.__eq__(other)


class PyupStatusBarApp(rumps.App):
    def __init__(self):
        super(PyupStatusBarApp, self).__init__(
            name="pyup",
        )

        # todo: these settings need to go into a preference window
        self.settings = {
            'paths': [
                os.path.join(
                    os.path.dirname(os.path.realpath(__file__)),
                    'test_files'
                )
                 # todo: during testing, replace this with an actual dir that holds the data
            ],
            'depth': 1,
            'key': ''
        }

        self.projects = []

        # todo:
        # build up the menu bar here
        # [ room for projects ]
        # --------------------- </ separator
        # Preferences
        # Quit

    # todo: this needs to be non blocking
    @rumps.timer(60 * 60)  # run every hour
    def sync(self, sender):
        if self.icon is None:
            self.icon = ICONS.GRAY
        try:
            insecure = False
            for path in self.settings['paths']:
                for item in os.listdir(path):
                    full_path = os.path.join(path, item)
                    if os.path.isdir(full_path):
                        project = Project(self, full_path)
                        print("have", full_path)
                        if project not in self.projects:
                            self.projects.append(project)
                            if project.needs_check:
                                project.check()
                                if project.is_valid:
                                    project.add()
                                    if project.insecure:
                                        insecure = True
            if insecure:
                self.icon = ICONS.RED
            else:
                self.icon = ICONS.GREEN
        except:
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    PyupStatusBarApp().run(
        debug=True
    )