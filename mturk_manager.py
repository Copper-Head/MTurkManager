'''
Mturk Manager.

This script makes it easy to upload new qualification types into Amazon MTurk.

Created by Ilia Kurenkov in 2014.
License:
http://opensource.org/licenses/MIT
'''

#===================== IMPORTS  ======================
import os
# regular expressions
import re
#import stuff from boto
from boto.mturk import question as mt_q
from boto.mturk.connection import MTurkConnection
from argparse import ArgumentParser


def main():
    '''Main driver function that gets excecuted if you run 
    "python mturk_manager.py" from command line.
    Uses argparser for command line arguments. 
    Run "mturk_manager.py -h" for details.
    '''
    # define some help strings for ArgParser
    program_description = 'This program loads qualification tests into MTurk.'
    dir_help = ('This argument specifies the folder from which to read '
                    'test properties and questions.')
    account_help = ('This specifies the key file from which '
                        'to read credential information.')
    # set up argument parser
    arg_parser = ArgumentParser(description=program_description)
    arg_parser.add_argument('testdir', help=dir_help)
    arg_parser.add_argument('account', help=account_help)
    cmd_arg = arg_parser.parse_args()

    # set up test directory path
    root = os.getcwd()
    if cmd_arg.testdir not in os.listdir(root):
        raise MissingFolderException(cmd_arg.testdir)

    test_root = os.path.join(root, cmd_arg.testdir)

    # load properties file
    properties_f_name = find_file('properties', test_root)
    properties = read_settings_file(properties_f_name)

    # load question and answer src files
    question_src = find_file('questions', test_root)
    question_xml, answer_xml = parse_question_file(question_src)

    # set up a connection to Mturk
    connection = create_mturk_connection(cmd_arg.account)

    # create qualification test
    connection.create_qualification_type(properties['name'],
                                         properties['description'],
                                         'Active',
                                         test=question_xml,
                                         answer_key=answer_xml,
                                         keywords=properties['keywords'],
                                         retry_delay=properties['retrydelayinseconds'],
                                         test_duration=properties['testdurationinseconds'])


def find_file(f_type, folder):
    '''Given a file type (basically an extension) and a folder in which to 
    search for this file type either returns a path to one file with the 
    correct extension (should be same as f_type argument) or lets user know
    that it cannot find any such file and halts the program.
    '''
    # make a list of files that fit
    candidates = [f for f in os.listdir(folder)
                  if f.endswith(f_type)]
    # make sure we actually found at least one file
    # if this is not the case, print NO_FILE_ERROR and halt
    NO_FILE_ERROR = ('No "{file_type}" files found. '
        'Cannot proceed without them')
    assert len(candidates) > 0, NO_FILE_ERROR.format(file_type=f_type)
    # if more than one file found, just alert the user about this
    # and let them know which file we are using
    if len(candidates) > 1:
        MULTIPLE_FILE_WARNING = ('More than one "{file_type}" file found. ' 
                                    'Using this one: {first_one}')
        print MULTIPLE_FILE_WARNING.format(file_type=f_type, 
                                            first_one=candidates[0])
    # return usable file path
    return os.path.join(folder, candidates[0])


def read_settings_file(f_path):
    '''Common function for reading in properties and key files.
    Given a file path returns a dictionary of key, value pairs read from 
    the file found at the path.
    Ignores comments and empty lines.
    '''
    # defined filtering function
    not_comment_empty = lambda line: not line.startswith('#') and line.strip()
    # open file for reading
    with open(f_path) as settings_file:
        # filter out comments and empty lines
        lines_to_read = filter(not_comment_empty, settings_file)
    # split lines across "=" character
    split_lines = (line.split('=') for line in lines_to_read)
    # remove all trailing whitespace
    no_trailing_whtspc = (map(str.strip, pair) for pair in split_lines)
    # convert to dictionary and return
    return dict(no_trailing_whtspc)


def parse_question_file(question_path):
    '''Given path to file with all the questions reads this file, extracts
    and parses the question info, then turns this into objects which will work
    with boto's create_qualification_type() method.
    '''
    with open(question_path, 'rU') as q_file:        
        # read in the whole file
        file_str = q_file.read()

    # create list of (question, answers) tuples
    questions_answers = split_by_question(file_str)
    # questions separately from answers
    questions, answers = zip(*tuple(questions_answers))
    # answers list must be pruned for empty members
    no_empty_answers = filter(None, answers)

    if no_empty_answers:
        # finally convert to QuestionForm and AnswerKey objects, but only if
        # there are in fact any entries with correct answers.
        # This handles cases where we want to score some (or all) questions manually.
        # Unfortunately current version of boto lacks
        # native AnswerKey class and its code raises an error if anything other 
        # than a string is passed for the answer key XML.
        # Thus we have to use get_as_xml() to turn our AnswerKey into a string
        return (mt_q.QuestionForm(questions), 
            AnswerKey(no_empty_answers).get_as_xml())
    # in case there are actually no entries for correct answers, return None as
    # second member of tuple
    return (mt_q.QuestionForm(questions), None)    


def split_by_question(file_str):
    '''Given a raw file string parses it into a list of mturk question and 
    question answer (which is defined here) tuples.
    '''
    # Define and compile regexes for searching through question file.
    question_search_str = ('Question (?P<type>\w*)\s*?'
        '(?P<content>.*?)'
        '(?P<answers>Answer.*?)'
        'Score (?P<score>\d+?)')
    qu_rgx = re.compile(question_search_str, flags=re.DOTALL)

    answers_search_str = ('Answer(?P<text>.*?)\s*?'
            'correct (?P<correct>\d*)')
    a_rgx = re.compile(answers_search_str, flags=re.DOTALL)

    # filter out all comments
    no_comments = re.sub('#.*', '', file_str)

    # extract question blocks
    parsed_questions = search_add_ids(no_comments, qu_rgx, 'q')

    # Having split the string into question items and attached IDs to them
    # we loop over collected info and feed it to different boto machinery
    for q_id, item in parsed_questions:
        # we start by splitting the answers field into individual answer items
        q_answers = search_add_ids(item['answers'], a_rgx, 'a')
        # needs (answer content, anwer identifier) tuples
        content_ids = [(answer['text'], answer_id) 
                            for answer_id, answer in q_answers]
        # which then get turned into a SelectionAnswer object
        selection_ans = mt_q.SelectionAnswer(selections=content_ids, 
                                            style=item['type'])
        # and then (all hail boto redundancy!!) into AnswerSpecification object
        specification = mt_q.AnswerSpecification(selection_ans)

        # make list of answer ids for acceptable answers
        acceptables = [answer_id for answer_id, answer in q_answers 
                                                if answer['correct'] == '1']
        # if the list isn't empty
        if acceptables:
            # turn that into our AnswerOption object
            answer_options = AnswerOption(acceptables, item['score'])
            correct_answers = QuestionAnswer(q_id, answer_options)
        else:
            correct_answers = None

        # QContent class has no init, we must use append_field to populate it
        q_content = mt_q.QuestionContent()
        q_content.append_field('Text', item['content'])

        yield (mt_q.Question(q_id, q_content, specification, is_required=True),
                correct_answers)


def search_add_ids(string, rgx, suffix):
    '''Takes a string, a regular expression and a suffix.
    Uses regular expression to search through string and creates
    a list of dictionaries from what it finds.
    Then generates a list of IDs of the same length as list of dictionaries 
    using the suffix argument.
    Returns the result of combining dictionaries with their corresponding IDs.
    '''
    # turn all matches to passe rgx into dictionaries where keys are taken 
    # from pattern names defined in rgx
    found_dicts = [match.groupdict() for match in rgx.finditer(string)]
    # define function for creating a suffix
    suffixer = lambda n: suffix + str(n)
    # turn this into ids by creating an iterable of numbers 1:length of dict + 1
    # then loop over this iterable applying suffixer to every member thereof
    IDs = map(suffixer, xrange(1, len(found_dicts) + 1))
    # combine these ID strings with the dictionaries
    return zip(IDs, found_dicts)


def create_mturk_connection(key_f_name):
    '''My wrapper for operations associated with creating a connection to mturk.
    Given an account folder path, and optionally a rootkey file name, tries to
    read it the appropriate key file settings for this account and open an
    MTurkConnection based on what it collects.
    '''
    # load secure keys
    keys = read_settings_file(key_f_name)
    # create connection and return 
    return MTurkConnection(aws_access_key_id=keys['AWSAccessKeyId'],
                           aws_secret_access_key=keys['AWSSecretKey'])


################################################################################
## Class definitions
################################################################################

# Since the official boto development is lagging behind our needs, I've created
# a couple of classes that are needed to bridge the gap

class AnswerKey(mt_q.ValidatingXML, list):
    schema_url = ('http://mechanicalturk.amazonaws.com/'
        'AWSMechanicalTurkDataSchemas/2005-10-01/AnswerKey.xsd')
    xml_template = ('<?xml version="1.0" encoding="UTF-8"?>\n'
        '<AnswerKey xmlns="{schema_url}">\n'
        '{answers}\n'
        '</AnswerKey>\n')

    def get_as_xml(self):
        items = '\n'.join(item.get_as_xml() for item in self)
        return self.xml_template.format(schema_url=self.schema_url, 
            answers=items)


class AnswerOption():
    def __init__(self, correct_ans, score):
        self.correct_answers = correct_ans
        self.score = score
        self.template = ('<AnswerOption>\n'
                        '{options}\n'
                        '</AnswerOption>')

    def get_as_xml(self):
        IDs = [mt_q.SimpleField('SelectionIdentifier', ID)
               for ID in self.correct_answers]
        fields = IDs + [mt_q.SimpleField('AnswerScore', self.score)]
        fields_combined = '\n'.join(f.get_as_xml() for f in fields)
        return self.template.format(options=fields_combined)


class QuestionAnswer(mt_q.Question):
    template = '<Question>\n{0}\n{1}\n</Question>'

    def __init__(self, identifier, options):
        self.identifier = mt_q.SimpleField('QuestionIdentifier', identifier)
        self.answer_options = options

    def get_as_xml(self):
        return self.template.format(self.identifier.get_as_xml(),
                                    self.answer_options.get_as_xml())


class MissingFolderException(Exception):
    MESSAGE = ('Unable to find the folder "{folder_name}".\n'
        'Please specify a valid folder name.\n'
        'It is case sensitive.')

    def __init__(self, folder):
        self.folder = folder

    def __str__(self):
        return self.MESSAGE.format(folder_name=self.folder)


#------------------------------------------------------------------------------
if __name__ == '__main__':
    main()
