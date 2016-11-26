This is Magicicada GUI!

A GTK+ frontend for the "Chicharra" part of Ubuntu One client.


HOWTO run it from source
------------------------

Just do, from where you branched the project:

    PYTHONPATH=$MAGICICADA_CLIENT_BRANCH:. bin/magicicada

(being $MAGICICADA_CLIENT_BRANCH the path of where you have
your working lp:magicicada-client)


HOWTO do a source release
-------------------------

 * edit setup.py and increment the version number.
 * 'python setup.py sdist'
 * look at the contents of the tarball created in dist/ to be sure they are ok
 * step into the dist directory for the following commands
 * sign the tarball by a command like:
     gpg -a --detach-sign magicicada-VERSION.tar.gz
     this should create a file like magicicada-VERSION.tar.gz.asc
 * Upload the new release to launchpad with a command like:
     lp-project-upload magicicada VERSION magicicada-VERSION.tar.gz
 * Announce the release, ping someone to build updated packages for the PPA and Ubuntu.


HOWTO prepare an updated Ubuntu package
---------------------------------------

 * bzr get lp:ubuntu/magicicada
 * cd magicicada
 * uscan --verbose --rename (this gets the new upstream release from launchpad)
 * bzr merge-upstream ../magicicada_VERSION.orig.tar.gz --version=VERSION lp:magicicada

Now, the action depends on where to release: You will need to build versions
for lucid (for the PPA) and for the current dev release of Ubuntu. On each
case you'll need to edit debian/changelog and check version, distro, etc.

For the chicharrero sPPA:

  * The version depends on the distro:

      magicicada-VERSION-0ubuntu1~lucid1
      magicicada-VERSION-0ubuntu1~maverick1

  * debuild -S -sa
  * dput ppa:chicharreros/ppa <source.changes>


For the version to upload to Ubuntu Universe:

  * The version number would be magicicada-VERSION-0ubuntu1.
  * Don't forget to put "LP: #XXXXXX" in the message, LP does stuff with it
  * Push the changes to lp:~USER/ubuntu/maverick/magicicada/VERSION-update
  * Open it with 'bzr lp-open', propose it to merge, and set
    the 'reviewer' to "ubuntu-sponsors".
  * File a bug in Launchpad:

        http://bugs.launchpad.net/ubuntu/+source/magicicada/+filebug

    and subscribe it (not "assign") to 'ubuntu-sponsors'
