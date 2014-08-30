# encoding: UTF-8

Vagrant.configure('2') do |config|
  config.vm.box = 'hashicorp/precise64'
  config.vm.provision 'shell', inline: <<-EOF
    apt-get update
    apt-get -y install build-essential git ruby1.9.1-dev python-dev curl vim wget
    gem install --no-ri --no-rdoc fpm
    # super secure installation tools
    curl https://bootstrap.pypa.io/get-pip.py | python
    curl http://get.docker.io | bash
  EOF

  config.vm.provider "virtualbox" do |v|
    v.memory = 2048
    v.cpus = 2
  end

  config.vm.define 'giftwrap' do |c|
    c.vm.host_name = 'giftwrap'
  end
end
