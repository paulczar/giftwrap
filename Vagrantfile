# encoding: UTF-8

Vagrant.configure('2') do |config|
  config.vm.box = 'hashicorp/precise64'
  config.vm.provision 'shell', inline: <<-EOF
    apt-get update
    apt-get -y install build-essential git ruby1.9.1-dev python-pip python-dev curl vim wget
    gem install --no-ri --no-rdoc fpm
    curl http://get.docker.io | bash
  EOF

  config.vm.define 'giftwrap' do |c|
    c.vm.host_name = 'giftwrap'
  end
end
