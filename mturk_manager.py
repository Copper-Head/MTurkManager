
# This program is free and subject to the conditions of the MIT license.
# If you care to read that, here's a link:
# http://opensource.org/licenses/MIT

#===================== IMPORTS --- SETUP --- GLOBAL VARS ======================
import os
import sys
import re

#import stuff from boto
from boto.mturk.question import *


def parse_question_file(file_name):
    q_rgx = re.compile('Question (\d+) (.+)\s*(.+)')
    a_rgx = re.compile('Answer (.+)\s*(.+)')
    ans_rgx = re.compile('(Answer.+?)(?=Question|END)', flags=re.DOTALL)
    with open(file_name, 'rU') as q_file:
        q_file_str = q_file.read()
        questions = q_rgx.findall(q_file_str)
        answers = ans_rgx.findall(q_file_str)
        #print questions
        #print answers
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


#================================= __MAIN__ ===================================
def main():
    with open('test.xml', 'w') as test:
        test.write(parse_question_file('english.questions').get_as_xml())

#------------------------------------------------------------------------------
if __name__ == '__main__':
    main()

