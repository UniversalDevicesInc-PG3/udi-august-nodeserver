
## Configuration

In polyglot on the nodesever AugustLock set the following configuration options:

   - email - email to access August Account
   - password - password to access August Account
   - install\_id - generate a random uuid (11111111-1111-1111-1111-111111111111)
   - tokenFilePath - Path and Filename were the tokenFile should be generated ( /var/polyglot/nodeservers/AugustLock/token.txt )
                     The directory must exist and the user running polyglot must have read/write access

The first time your run the nodeserver, you should receive a validation code by email, enter the validation code on August Node in ISY994 and click Send Validation. 

Once your get a message in the log saying it has been validated, restart the node server and your lock should appear.
