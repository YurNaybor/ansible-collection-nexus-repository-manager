# Ansible Collection - slangdaddy.nexus_repository_manager

This collection provides tools to configure Sonatype Nexus (3) Repository
Manager.

The implementation is currently very limited and does not contain proper error
handling, as the aim here is currenly to provide an easy way to setup a local
proxy for repositories used in development. No production ready


## Tested Nexus Versions:

* 3.41.1

Note that there seems to be a bug with Nexus 3.41.1, where Docker repositories
that have been configured using this module (or the API in general), are
failing API calls after restarting Nexus.
