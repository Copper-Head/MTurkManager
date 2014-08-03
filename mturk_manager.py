#This script makes it easy to create and delete new qualification types in MTurk.
#Please note that deleting qualification types is c
# http://opensource.org/licenses/MIT

#===================== IMPORTS --- SETUP --- GLOBAL VARS ======================
import os
import sys
import re

#import stuff from boto
from boto.mturk import question as mt_q
from boto.mturk.connection import MTurkConnection
from argparse import ArgumentParser

#================================= __MAIN__ ===================================


def main():
    # define some strings for ArgParser
    progr_descr = 'This program loads native qualification tests into MTurk.'
    lang_help = 'This specifies the folder from which to read questions and answers.'
    account_help = 'This specifies the folder from which to read credential information.'
    # set up argument parser
    arg_parser = ArgumentParser(description=progr_descr)
    arg_parser.add_argument('language', help=lang_help)
    arg_parser.add_argument('account', help=account_help)
    cmd_arg = arg_parser.parse_args()

    # set up language directory
    root = os.getcwd()
    if cmd_arg.language not in os.listdir(root):
        raise MissingFolderException(cmd_arg.language)

    lang_root = os.path.join(root, cmd_arg.language)

    # load properties file
    properties_f_name = find_file('properties', lang_root)
    properties = read_settings_file(properties_f_name)

    # load question and answer src files
    question_src = find_file('questions', lang_root)
    question_xml, answer_xml = parse_question_file(question_src)

    # set up a connection.
    connection = create_mturk_connection(os.path.join(root, cmd_arg.account))

    # create qualification test
    connection.create_qualification_type(properties['name'],
                                         properties['description'],
                                         'Active',
                                         test=question_xml,
                                         answer_key=answer_xml,
                                         keywords=properties['keywords'],
                                         retry_delay=properties['retrydelayinseconds'],
                                         test_duration=properties['testdurationinseconds'])


def parse_question_file(file_name):

    with open(file_name, 'rU') as q_file:        
        # read in the whole file
        file_str = q_file.read()

    # create list of (question, answers) tuples
    questions_answers = individual_questions(file_str)
    # questions separately from answers
    questions, answers = zip(*tuple(questions_answers))
    # finally convert to QuestionForm and AnswerKey objects
    # Unfortunately current version of boto lacks
    # native AnswerKey class and its code raises an error if anything other 
    # than a string is passed for the answer key XML.
    # Thus we have to use get_as_xml() to turn our AnswerKey into a string
    return (QuestionForm(questions), AnswerKey(answers).get_as_xml())    


def individual_questions(file_str):

    # Define and compile regexes for searching through question file.
    question_search_str = ('Question (?P<type>\w*)\s*?'
        '(?P<content>.*?)'
        '(?P<answers>Answer.*?)'
        'Score (?P<score>\d+?)')
    qu_rgx = re.compile(question_search_str, flags=re.DOTALL)

    answers_search_str = ('Answer(?P<text>.*?)\s*?'
            'correct (?P<correct>\d*)')
    a_rgx = re.compile(answers_search_str, flags=re.DOTALL)

    parsed_questions = split_add_ids(file_str, qu_rgx, 'q')

    # Having split the string into question items and attached IDs to them
    # we loop over collected info and feed it to different boto machinery
    for q_id, item in parsed_questions:
        # we start by splitting the answers field into individual answer items
        q_answers = split_add_ids(item['answers'], a_rgx, 'a')
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
                                                    if ans['correct'] == '1']
        # turn that into our AnswerOption object
        answer_options = AnswerOption(acceptables, item['score'])

        # QContent class has no init, we must use append_field to populate it
        q_content = mt_q.QuestionContent()
        q_content.append_field('Text', item['content'])

        yield (mt_q.Question(q_id, q_content, specification, is_required=True),
                QuestionAnswer(q_id, answer_options))


def split_add_ids(string, rgx, suffix):

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


def find_file(f_type, folder):
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


def create_mturk_connection(account_folder):
    # load secure keys
    key_f_name = os.path.join(account_folder, 'rootkey.csv')
    keys = read_settings_file(key_f_name)
    # create connection and return 
    return MTurkConnection(aws_access_key_id=keys['AWSAccessKeyId'],
                           aws_secret_access_key=keys['AWSSecretKey'])


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


class AnswerKey(ValidatingXML, list):
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
        IDs = [SimpleField('SelectionIdentifier', ID)
               for ID in self.correct_answers]
        fields = IDs + [SimpleField('AnswerScore', self.score)]
        fields_combined = '\n'.join(f.get_as_xml() for f in fields)
        return self.template.format(options=fields_combined)


class QuestionAnswer(Question):
    template = '<Question>\n{0}\n{1}\n</Question>'

    def __init__(self, identifier, options):
        self.identifier = SimpleField('QuestionIdentifier', identifier)
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
