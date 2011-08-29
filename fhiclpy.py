#==========FHICLPY===============================================================================
# AUTHOR: Ryan Putz
# This is a python-based parser which utilizes the PyParsing module by Paul McGuire.
# It is a top-down, recursive descent parser.
#
# IMPLEMENTATION DIFFERENCES:
#    This version of fhicl-py allows for the overriding of prolog entries by non-prolog entries
#    of the same name. This change is in accordance with git commit #69b72b863987c8b52ca781f1823c2c447b887ccf
#    of fhicl-cpp wherein a similar modification was made.
# 
# CURRENT ISSUES: Some ambiguous error messages; No errors thrown for incorrect unquoted string
#                 and leading zero cases.
#================================================================================================
import sys, string, re, decimal, ast
import os.path
import pyparsing as pp

sys.path.append("/home/putz/fhicl/fhicl/fhicl-py")
sys.path.append("/home/putz/fhicl/fhicl/fhicl-py/orderedDict.py")

#Different from Python 7.2's built-in OrderedDict.
#This class is compatible with Python 4.3 up to 7.x
#Don't know about Python 3.x
from orderedDict import OrderedDict
from decimal import *

#========================================================
#                 CUSTOM EXCEPTIONS
#========================================================
class INVALID_TOKEN(Exception):
   def __init__(self, stmt):
      self.msg = "PARSE ERROR: Invalid token detected! " + stmt
   def __str__(self):
      return repr(self.msg)

class INVALID_KEY(Exception):
   def __init__(self, stmt):
      self.msg = stmt
   def __str__(self):
      return repr(self.msg)

class INVALID_INCLUDE(Exception):
   def __init__(self, stmt):
      self.msg = "PARSE ERROR: Invalid #include statement detected! " + stmt
   def __str__(self):
      return repr(self.msg)

class PARSE_FAILURE(pp.ParseSyntaxException):
   def __init__(self, stmt):
      self.msg = stmt
   def __str__(self):
      return repr(self.msg)

class ILLEGAL_STATEMENT(Exception):
   def __init__(self, stmt, i):
      self.msg = "PARSE ERROR: Illegal statement found before PROLOG at line " + str(i) + " => " + stmt
   def __str__(self):
      return repr(self.msg)

class INVALID_ASSOCIATION(Exception):
   def __init__(self, stmt):
      self.msg = "PARSE ERROR: Invalid syntax for an association! " + stmt
   def __str__(self):
      return repr(self.msg)

#========================================================
#           PARSE BEHAVIOR FUNCTIONS/METHODS
#========================================================

#joining two dictionaries (recursive)
def join(A, B):
    if not isinstance(A, dict) or not isinstance(B, dict):
        return A or B
    return dict([(a, join(A.get(a), B.get(a))) for a in set(A.keys()) | set(B.keys())])

#Function for converting string to int
def convertInt(origString, loc, tokens):
   return int(tokens[0])

#Function for converting string to long
def convertLong(origString, loc, tokens):
   getcontext().prec = len(tokens[0]) - tokens[0].index(".")
   return long(tokens[0])

#Function for converting string to float
def convertFloat(origString, loc, tokens):
   getcontext().prec = len(tokens[0]) - tokens[0].index(".")
   #if representable as an int, do it
   if (int(float(tokens[0])) == float(tokens[0])):
      return int(Decimal(tokens[0]))
   else:
      return float(Decimal(tokens[0]))

#Function for converting string to complex
def convertComplex(tokens):
   cmplx = ast.literal_eval(tokens[0])
   return cmplx
   
#Function for converting string to scientific notation
def convertSci(origString, loc, tokens):
   getcontext().prec = len(tokens[0]) - tokens[0].index(".")
   number = str(float(Decimal(tokens[0])))
   number = re.sub(r'([Ee])\+',r'\1',number)
   if int(Decimal(number)) == float(number): 
      number = str(int(Decimal(number)))
   return '%s' % (number,)
   
#Function for converting string to hexadecimal 
def convertHex(origString, loc, tokens):
   #return int(tokens[0], 16)
   return tokens[0]
#Function for converting to a list
def convertList(tokens):
   return tokens.asList()

#checks the passed string for malformed, unquoted strings.
def checkStr(origString, loc, tokens):
   strg = origString[origString.index(tokens[0]) + len(tokens[0]):len(origString)]
   strg = strg.replace("\n", "")
   if strg.count(":") == 0 and strg.count("::") == 0 and strg.count(".") == 0 and strg.count("[") == 0 and strg != "":
      if tokens[0] in strg or tokens != strg:
         raise INVALID_TOKEN("Invalid Token @ " + strg)
   elif str(tokens[0])[0].isdigit():
         raise INVALID_TOKEN("Invalid Token @ " + tokens[0])
   return tokens

#Raises an INVALID_TOKEN exception
def raiseInvalidToken(origString, loc, tokens):
   raise INVALID_TOKEN("Invalid Token @ " + tokens)

#hname storage:
#Items in this list are left-hand heirarchical names
#that are to be removed from the parameter set after
#being resolved
delItems = []


#========================================================
#                       GRAMMAR
#========================================================
# Leading "NoMatch()" elements indicate what to do if the 
# parser can't match a token once it has committed to a type

#Comments:
#Allows combined grammar to ignore commented lines
comment= pp.oneOf('# //') + pp.ZeroOrMore(pp.Word(r'*')) + pp.LineEnd()
pcomment= pp.Regex(r'\#.*') + pp.LineEnd()
ccomment= pp.Regex(r'//.*') + pp.LineEnd()

#Parameter Set Grammar:
def Syntax():

   #(Bottom)
   # --BOOLEAN--
   true= pp.Word("True")
   false= pp.Word("False")
   bool= true | false

   # --MISC--
   ws= pp.Regex(r'\s*').suppress()
   lparen= pp.Literal("(").suppress()
   rparen= pp.Literal(")").suppress()
   colon= pp.NoMatch().setName("colon") | (ws + ':' + ws)
   local= pp.Regex(r'@local::')
   db= pp.Regex(r'@db::')

   # --NUMBER--
   null= pp.Word('nil')
   infinity= pp.oneOf( 'infinity' '+infinity' '-infinity')
   integer= pp.Word(pp.nums).setParseAction(convertInt)
   float= pp.Regex(r'[\d]*[.][\d*]').setParseAction(convertFloat)
   hex= pp.Regex(r'(0x|$|0X)[0-9a-fA-F]+').setParseAction(convertHex)
   bin= pp.Regex(r'(0b)[01]+')
   sci= pp.Regex(r'[0-9\W]*\.[0-9\W]*[eE][0-9]*').setParseAction(convertSci)
   simple= float | integer
   complex= pp.Combine(lparen + ws + simple + ws + "," + ws + simple + ws + rparen).setParseAction(convertComplex)
   number=  pp.NoMatch().setName("number") | pp.MatchFirst(sci | complex | hex | simple | infinity)
        
   # --STRING--
   uquoted= pp.NoMatch().setName("unquoted string") | pp.Word(pp.alphas+'_', pp.alphanums+'_').setParseAction(checkStr)
   squoted = pp.Regex(r'\'(?:\\\'|[^\'])*\'', re.MULTILINE)
   dquoted = pp.Regex(r'\"(?:\\\"|[^"])*\"', re.MULTILINE)
   string= pp.NoMatch().setName("string") | pp.MatchFirst(dquoted | squoted | uquoted)
   name= pp.NoMatch().setName("name") | uquoted
   dot= pp.Regex(r'[.]') + name
   bracket= pp.Regex(r'\[[\d]\]')
   #Added "Combine" to recognize hname token
   hname= pp.NoMatch().setName("hname") | pp.Combine(name + (bracket|dot) + pp.ZeroOrMore(bracket|dot))
   id= pp.NoMatch().setName("name or hname") | pp.MatchFirst(hname | name).setName("ID")
   ref= pp.NoMatch().setName("reference") | (pp.Combine(local - id) | pp.Combine(db - id))

   # --ATOM|VALUE--
   atom= pp.NoMatch().setName("atom") | pp.MatchFirst(ref | number | string | null | bool).setName("atom")
   #table & seq must be forwarded here so that a definition for value can be created
   table= pp.Forward()
   seq= pp.Forward()
   value= pp.NoMatch().setName("value") | pp.MatchFirst(atom | seq | table).setName("value")

   # --ASSOCIATION-
   association= pp.NoMatch().setName("association") | (id - colon - value)
        
   # --SEQUENCE--
   seq_item= pp.NoMatch().setName("seq_item") | pp.MatchFirst(value | pp.Regex(r',').suppress())
   seq_body= pp.nestedExpr('[', ']', seq_item) 
   #filling in forwarded definition
   seq << seq_body

   # --TABLE--
   table_item= pp.NoMatch().setName("association") | pp.MatchFirst(association | pp.Regex(r'\s'))
   table_body= pp.nestedExpr('{', '}', table_item)
   #filling in forwarded definition
   table<< table_body

   # --DOCUMENT--
   doc_body= pp.NoMatch().setName("association") | pp.ZeroOrMore(table_item)
   document= doc_body
   return document
   #(Top)

#========================================================
#                      END GRAMMAR
#========================================================

#========================================================
#                      FUNCTIONS/METHODS
#========================================================

#Is the passed string an include statement?
def isInclude(s):
        exists = s.count("#include") > 0
        if exists:
           BoL = s.index("#include") == 0
           if BoL:
              space = (s.count(" ") >= 1 and s.index(" ") == 8)
              if space:
                 return True
              else:
                 raise INVALID_INCLUDE(s + " is not a valid include statement.")
           else:
              return False
        else:
           return False

#Is the passed string a comment?
def isComment(s):
   if not(isInclude(s)):
      if (s.count("#") > 0 or s.count(r'//') > 0):
         if s.count("#") > 0:
            if s.index("#") == 0:
               return True
            else:
               return False
         elif s.count(r'//') > 0:
            if s.index(r'//') == 0:
               return True
            else:
               return False
      else:
         return False
   else:
      return False     

#Is the passed string a reference?
def isRef(s):
   return str(s).count("::") > 0 and str(s).count("@") > 0

#Is the passed string an hname?
def isHName(s):
        return (str(s).count(".") > 0 or (str(s).count("[") > 0 and str(s).count("[") == str(s).count("]")))

#Checks to see if a document (string) is considered "empty"
#A document is considered "empty" if it contains only comments or only (a) prolog(s).
def isEmptyDoc(s):
        content = s.splitlines(1)
        #if there's nothing in s
        if len(content) == 0:
           return True
        else:
           for line in content:
              #broken!
              if (not(isComment(line)) and line != "" and line != "\n"):
                 return False
        return True

#Function which looks for matching pairs of single or double quotes
def isString(s):
   s = str(s)
   if s.count("'") == 2:
      if s.find("'") == 0 and s.rfind("'") == len(s) - 1:
         return True
   elif s.count('"') == 2:
      if s.find('"') == 0 and s.rfind('"') == len(s) - 1:
         return True
   else:
      return False

#Reads External file and returns the contents
def handleInclude(s):
   name = s.split('"')
   try:
      name = name[1]
      file = open(name)
      fileContents = file.read()
      return fileContents
   except:
      raise INVALID_INCLUDE(s + " is not a valid include statement.")
              
#Function to handle includes before grammar parsing begins 
#Doesn't handle past 3 levels of includes...     
def checkIncludes(s):
        content = s.splitlines(1)
        pcontent = str("")
        i = 0
        while i < len(content):
           #Is the line an include?
           if isInclude(content[i]):
              fileContents = checkIncludes(handleInclude(content[i]))
              if fileContents != None:
              #   if fileContents.count("#include") > 0:
              #      fileContents = handleInclude(fileContents)
                 pcontent += fileContents
           #Otherwise just add it to the parsed content
           else:
              #Either raise an error if we're picky about include syntax
              #OR treat it as a comment

              #raise INVALID_INCLUDE("Syntax error on line " + str(i))
              pcontent += content[i]
           i += 1
        #return the parsed content
        return pcontent
#Function that determines which type of indexing is being used in an hname.
#The two options are DOT(".") index or BRACKET("[]") index.
#The decision is made based on existence and location within a string
def detIndType(s):
   s = str(s)
   b = s.find("[")
   d = s.find(".")
   if b == -1 and d > -1:
      return "."
   if d == -1 and b > -1:
      return "["
   if b == -1 and d == -1:
      #raise KeyError(s + " invalid hname indexing")
      return ""
   elif ( d <= b):
      return "."
   elif ( b <= d):
      return "["

#Utility function for stripping off the closing bracket in bracket notation
def stripCloseB(s):
   s = str(s).split("]", 1)
   s = s[0] + s[1]
   return s

#Function that handles look-up of hname references
def handleRHname(s, d):
   indexChar = detIndType(s)
   if indexChar != "":
      if indexChar == "[":
         s = stripCloseB(s)
      s = s.split(indexChar, 1)
      key = s[0]
      rest = s[1]
      if type(d) is list and len(d)-1 > int(key):
         return handleRHname(rest, d[int(key)])
      elif key in d:
         return handleRHname(rest, d[key])
      else:
         raise KeyError(key + " in " + str(d))
   elif s in d:
      return d[s]
   else:
      raise KeyError(s + " in " + str(d))

#Function that handles overrides using hnames
def handleLHname(s, d, v):
   indexChar = detIndType(s)
   if indexChar != "":
      if indexChar == "[":
         s = stripCloseB(s)
      s = s.split(indexChar, 1)
      key = s[0]
      rest = s[1]
      return handleRHname(rest, d[key])
   else:
      if type(d) is list:
         index = int(s)
         if index > (len(d) - 1):
            d.append(v)
         else:
            d[int(s)] = v
         return d
      else:
         #change to d[s] = v to change behavior
         #move "return d" from 2 lines up to outside if/else
         
         #problem occurs here!!!
         #Fixed - ish
         return dict(zip(list(s), list(str(v))))

def resolveRef(d, p, v):
   #Found a reference
   if isRef(v):
      key = v.split("::")[1]
      indChar = detIndType(key)
      #if it's an HName
      #Can probably change this to use "IsHName(s)"
      if indChar != "":
         #If it's a brace index, strip off the closing brace
         if indChar == "[":
            key = stripCloseB(key)
         #split at the indexing character
         testKey = key.split(indChar, 1)[0]
         #check to see if the leading name is in the document dictionary
         if testKey in d:
            #if so, recursively handle the hname
            v = handleRHname(key, d)
            #d[k] = handleRHname(key, d)
         #else check to see if the key is in the prolog dictionary
         elif testKey in p:
            #if so, recursively handle the hname
            #d[k] = handleRHname(key, p)
            v = handleRHname(key, p)
         else:
            #Otherwise, error out
            raise KeyError("In resolveRef: " + testKey)
      #If it's not an hname
      #check to see if the name exists in d
      elif key in d:
         v = d[key]
      #else check to see if the name exists in p
      elif key in p:
         v = p[key]
      else:
         raise KeyError("In resolveRef: " + key)
   return v

def resolveHName(d, p, k, v):
   #RETURN A KEY
   #If it's an hname
   if isHName(k):
      #determine which type of indexing is being used next
      newKey = k
      splitChar = detIndType(k)
      #If there is a type of index being used 
      if splitChar != "":
         #If it's bracket indexing, strip off the closing bracket
         if splitChar == "[":
            newKey = stripCloseB(k)
         #Split on the splitChar
         newKey = newKey.split(splitChar, 1)
         #Two pieces: chunk before split char => newKey
         #            chunk after split char => rest
         rest = newKey[1]
         newKey = newKey[0]
         #If the newKey is in the PSet
         if newKey in d:
            #Handle hname override
            d[newKey] = handleLHname(rest, d[newKey], v)
            #delItems.append(k)
         #Else if newKey is in the Prolog
         elif newKey in p:
            #Handle hname override 
            d[newKey] = handleLHname(rest, p[newKey], v)
         delItems.append(k)
   return d

#Function that checks the input string for illegal statements before prologs
def orderCheck(s):
   content = s.splitlines();
   i = 0
   while i < len(content) - 1: 
      if not(isComment(content[i])) and content.count("BEGIN_PROLOG") > 0:
         j = content.index("BEGIN_PROLOG")
         if j > i:
            raise ILLEGAL_STATEMENT(content[i], i)
      i += 1
   return True

#Construction of a parameter set. Used for both the prolog and document body
def buildPSet(toks, p={}):
   #We're creating a dictionary, so we'll need keys and values to map to them:
   newDict = {}
   key = ""
   val = ""
   #Step through the parse tree (toks)
   while len(toks) > 0:
      #Checks to ensure that there are tokens to process and that each line is a valid association
      #This check works because all non-association elements have been removed by this point.
      #Could potentially dump this check all together as anything that doesn't have a ":" in it at this point is invalid
      #NO! Necessary for dual-useage in assembling prolog
      if len(toks) > 1 and str(toks[1]) == (":"):
         #keys.append(toks.pop(0)) #pop the "key" token and append it to the list of keys
         key = toks.pop(0)
         toks.pop(0) #dumping the ":"
         #Still have tokens left?
         if len(toks) > 0:
            #If it's not a quoted string
            if not isString(toks[0]):
               #Reference checking/handling
               if str(toks[0]).count("@") > 0 and str(toks[0]).index("@") == 0:
                  val = toks.pop(0)
               #Sequence/Table checking/handling
               #In the parse tree of tokens, fhicl sequences and tables are both denoted by brackets ("[]")
               #Tables, however, contain associations, so we can make a distinction based on if the body contains (":")
               elif str(toks[0]).count("[") > 0 and str(toks[0]).count("[") == str(toks[0]).count("]"):
                  #In the parse tree of tokens, fhicl sequences and tables are both denoted by brackets ("[]")
                  #Tables, however, contain associations, so we can make a distinction based on if the body contains (":")
                  #These 4 lines of code handle the case of "I have a sequence of tables"
                  #I.E. seq:[ { a:1 b:2 }, { c:3 d:4 } ]
                  #Wherein the parse tree treats everything as lists of tokens until we assemble them here.
                  #So we can't just blindly check for (":"), and we have to ensure that we're not calling it a table
                  #if it's really a sequence of tables.
                  secBrack = -1
                  if str(toks[0]).count("[") > 1:
                     strg = str(toks[0]).split("[", 1)[1]
                     secBrack = strg.index("[")
                  #Table
                  if str(toks[0]).count(":") > 0 and (secBrack == -1 or str(toks[0]).index(":") < secBrack):
                     val = buildPSet(toks.pop(0), p)
                  else:
                     #Manually assemble list, checking to see if each element is a non-table value or a table body
                     val = []
                     for item in toks[0]:
                        if str(item).count(":") > 0:
                           val.append(buildPSet(item))
                        else:
                           val.append(item)
                     #done with that token, trash it.
                     toks.pop(0) 
               #Otherwise we have an unquoted string/numeric
               else:
                  val = toks.pop(0)
            #Otherwise it's a quoted string
            else:
               val = toks.pop(0)
               #Strip off the single or double quotes
               val = val[1:len(val)-1]
         #Otherwise the association is malformed
         else:
            raise INVALID_ASSOCIATION("Invalid Association @ " + str(toks) + "; Valid syntax => name : value")
      #Otherwise it's a BEGIN/END token
      else:
         val = toks.pop(0)
      val = resolveRef(newDict, p, val) 
      newDict = resolveHName(newDict, p, key, val)
      newDict[key] = val
   for item in delItems:
      del newDict[item]
      delItems.pop(0)
   return newDict

#Assembles a prolog string by stripping out START and END tokens.
def assemblePrologStr(s):
   prologStr = s.split("BEGIN_PROLOG")
   newStr = ""
   for item in prologStr:
      newStr += item.strip() + "\n"
   newStr = newStr.split("END_PROLOG")
   newStr2 = ""
   for item in newStr:
      newStr2 += item.strip() + "\n"
   return newStr2

#Takes a string, waves its wand, and out comes a complete parameter set.
def parse(s):
        try:
           prologs = []
           doc = Syntax()

           #ignoring comments
           doc.ignore(ccomment)
           doc.ignore(pcomment)

           content = str("")
           isEmpty = False
           #check for empty doc/only comments
           if isEmptyDoc(s):
              #If the document is empty, or just has comments/empty lines
              #Return an empty dictionary
              return dict()
           elif orderCheck(s):  
              #resolving include statements
              if s.count("#include") > 0:
                 s = checkIncludes(s)
              #handle prolog(s)
              if s.count("BEGIN_PROLOG") > 0:
                 prologStr = s[s.find("BEGIN_PROLOG")+12:s.rfind("END_PROLOG")-1]
                 s = s[s.rfind("END_PROLOG")+10:len(s)]
                 prologStr = assemblePrologStr(prologStr)
                 prologs = doc.parseString(prologStr)
                 prologs = buildPSet(prologs)
              #parse contents of file
              docStr = doc.parseString(s)
              #convert over to proper dictionary
              docStr = buildPSet(docStr, prologs)
              docStr = dict(docStr)
              #Covers the case of a malformed name in a single association, which makes up the entire document.
              if (docStr != {}): 
                 return dict(docStr)
              else:
                 raise INVALID_TOKEN("MALFORMED EXPRESSION(S)")
           else:
              raise ILLEGAL_STATEMENT(str(docStr))
        #Error handling
        except KeyError as e:
           print ("KEY_ERROR: " + "({0})".format(e))
        except INVALID_TOKEN as e:
           print ("INVALID_TOKEN: " + "({0})".format(e))
        except IOError as e:
           print ("IO_ERROR: " + "({0})".format(e))
        except ILLEGAL_STATEMENT as e:
           print ("ILLEGAL_STATEMENT: " + "({0})".format(e))
        except INVALID_INCLUDE as e:
           print ("INVALID_INCLUDE: " + "({0})".format(e))
        except INVALID_ASSOCIATION as e:
           print ("INVALID_ASSOCIATION: " + "({0})".format(e))
        except pp.ParseBaseException as e:
           print ("PARSE_EXCEPTION: " + "({0})".format(e))

#Default setup
if __name__ == '__main__':
        contents = sys.stdin.read()
        d= parse(contents)
        print d
