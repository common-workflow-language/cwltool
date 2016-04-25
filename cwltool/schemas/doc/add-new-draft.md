How to make a new draft version of the CWL spec

1. Duplicate prior draft-n directory to draft-n+1 in a branch
2. Update references to the new draft name.
3. Pull in the latest metaschema
     
     git subtree add -P draft-4/salad schema_salad_repo/master

4. In the reference implementation (cwltool): make a new branch, and update the
   subtree checkout of the spec:
   
     git subtree merge -P cwltool/schemas/ cwl_repo/draft-4
   
   Where `cwl_repo` is the remote repository for the CWL specifications.
4. In the reference implementation, teach it about the new draft version:

  a. Edit `cwltool/update.py`: append a new entry to the updates dictionary and
     change the previous last version to point to an update function
  b. Edit `cwltool/process.py`: update `get_schema` to look in the new
     directory
  c. Edit `setup.py` to include the new schemas in the `package_data` stanza
