#This script makes it easy to create and delete new qualification types in MTurk.
#Please note that deleting qualification types is c
# http://opensource.org/licenses/MIT

#===================== IMPORTS --- SETUP --- GLOBAL VARS ======================
import os
import sys
import re

#import stuff from boto
from boto.mturk.question import *
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
    question_xml = parse_question_file(question_src)
    answer_src = find_file('answers', lang_root)
    answer_xml = parse_answer_file(answer_src)

    print question_xml
# set up a connection.
#     connection = create_mturk_connection(os.path.join(root, cmd_arg.account))

# # create qualification test
#     connection.create_qualification_type(name=properties['name'],
#                                          description=properties['description'],
#                                          test=question_xml,
#                                          answer_key=answer_xml,
#                                          status='Active',
#                                          keywords=properties['keywords'],
#                                          retry_delay=properties['retrydelayinseconds'],
#                                          test_duration=properties['testdurationinseconds'])


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
        self.correct_ans = correct_ans
        self.score = score
        self.template = ('<AnswerOption>\n'
            '{options}\n'
            '</AnswerOption>')

    def get_as_xml(self):
        IDs = [SimpleField('SelectionIdentifier', ID)
               for ID in self.correct_ans]
        fields = IDs + [SimpleField('AnswerScore', self.score)]
        fields_combined = '\n'.join(f.get_as_xml() for f in fields)
        return self.template.format(options=fields_combined)


class QuestionAnswer(Question):
    template = '<Question>\n{0}\n{1}\n</Question>'

    def __init__(self, identifier, options):
        self.identifier = SimpleField('QuestionIdentifier', identifier)
        #self.answer_options = [opt.get_as_xml() for opt in options]
        self.answer_options = options

    def get_as_xml(self):
        return self.template.format(self.identifier.get_as_xml(),
                                    self.answer_options.get_as_xml())


def parse_answer_file(file_name):
    q_rgx = re.compile('Question (.*)')
    score_rgx = re.compile('Score (.*)')
    ans_rgx = re.compile('(Answer.+?)(?=Score)', flags=re.DOTALL)
    a_rgx = re.compile('Answer (.+)')
    with open(file_name, 'rU') as ans_file:
        ans_file_str = ans_file.read()
        questions = q_rgx.findall(ans_file_str)
        scores = score_rgx.findall(ans_file_str)
        answers = ans_rgx.findall(ans_file_str)
        assert len(questions) == len(answers) == len(scores)
    question_list = []
    for indx in xrange(len(questions)):
        q_answers = a_rgx.findall(answers[indx])
        answer_opts = AnswerOption(q_answers, scores[indx])
        question_list.append(QuestionAnswer(questions[indx], answer_opts))
    return AnswerKey(question_list)


def parse_question_file(file_name):
    q_rgx = re.compile('Question (\d+) (.+)\s*(.+)')
    a_rgx = re.compile('Answer (.+)\s*(.+)')
    ans_rgx = re.compile('(Answer.+?)(?=Question|END)', flags=re.DOTALL)
    with open(file_name, 'rU') as q_file:
        q_file_str = q_file.read()
        questions = q_rgx.findall(q_file_str)
        answers = ans_rgx.findall(q_file_str)
        assert len(questions) == len(answers)
    question_list = []
    for indx in xrange(len(questions)):
        q_id = questions[indx][0]
        q_type = questions[indx][1]

        q_content = QuestionContent()
        q_content.append_field('Text', questions[indx][2])

        q_answers = a_rgx.findall(answers[indx])
        selection_ans = SelectionAnswer(
            selections=[(x[1], x[0]) for x in q_answers],
            style=q_type)
        question_list.append(Question(q_id,
                                      q_content,
                                      AnswerSpecification(selection_ans),
                                      is_required=True))
    return QuestionForm(question_list)


def find_file(f_type, folder):
    NO_FILE_ERROR = 'No "{0}" files found. Cannot proceed without them'
    MULTIPLE_FILE_WARNING = 'More than one "{0}" file found. Using this one: {1}'
    candidates = [f for f in os.listdir(folder)
                  if f.endswith(f_type)]
    assert len(candidates) > 0, NO_FILE_ERROR.format(f_type)
    if len(candidates) > 1:
        print MULTIPLE_FILE_WARNING.format(f_type, candidates[0])
    return os.path.join(folder, candidates[0])


def create_mturk_connection(account_folder):
# load secure keys
    key_f_name = os.path.join(account_folder, 'rootkey.csv')
    keys = read_settings_file(key_f_name)
# create connection
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


class MissingFolderException(Exception):
    MESSAGE = ('Unable to find the folder "{}".\n'
        'Please specify a valid folder name.\n'
        'It is case sensitive.')

    def __init__(self, folder):
        self.folder = folder

    def __str__(self):
        return self.MESSAGE.format(self.folder)


def delete_qualification():
    pass


#------------------------------------------------------------------------------
if __name__ == '__main__':
    main()
