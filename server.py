import asyncio, json, time, os, logging, sys

SERVERS = ['Alford', 'Ball', 'Hamilton', 'Holiday', 'Welsh']
HOST = '127.0.0.1'
PORT = {
    'Alford': 8888,
    'Ball': 8889,
    'Hamilton': 8890,
    'Holiday': 8891,
    'Welsh': 8892
}
NEIGHBORS = {
    'Alford': ['Hamilton', 'Welsh'],
    'Ball': ['Holiday', 'Welsh'],
    'Hamilton': ['Holiday', 'Alford'],
    'Welsh': ['Alford', 'Ball'],
    'Holiday': ['Ball', 'Hamilton']
}

def no_wsp(unit):
    return unit.strip()

class Server:

    class ServerProtocol(asyncio.Protocol):
        def __init__(self, server_protocol):
            self.server_protocol = server_protocol
            self.peername = None

        def connection_made(self, transport):
            self.peername = transport.get_extra_info('peername')
            print('Connection from {}'.format(self.peername))
            logging.info('Connection from {}.'.format(self.peername))
            self.transport = transport

        def data_received(self, data):
            # parse the data received and log the info
            user_response = data.decode()
            logging.info(user_response)
            msg = user_response.split(' ')

            # run function based on what command is requested
            if no_wsp(msg[0].upper()) == 'IAMAT':
                task = asyncio.ensure_future(self.iamat_message(msg))
            elif no_wsp(msg[0].upper()) == 'WHATSAT':
                task = asyncio.ensure_future(self.whatsat_message(msg))
            elif no_wsp(msg[0].upper()) == 'AT':
                task = asyncio.ensure_future(self.at_message(msg))
            else:
                self.invalid_command(msg)
            #except Exception as exc:
            #    response = ('The coroutine raised an exception: {!r}'.format(exc))
            #    self.transport.write(response.encode('utf-8'))
            #    self.transport.close()

        def connection_lost(self, exc):
            print('Connection {} dropped.'.format(self.peername))
            logging.info('Connection {} dropped.'.format(self.peername))

        def invalid_command(self, data):
            error = ('? %r' % (data))
            logging.info(error)
            self.transport.write(error.encode('utf-8'))

        def parsed_location(self, loc):
            split = 0
            lat = 0.0
            lon = 0.0
            if '-' and '+' in loc:
                if loc.rfind('-') > loc.rfind('+'):
                    split = loc.rfind('-')
                else:
                    split = loc.rfind('+')
            elif '-' in loc:
                split = loc.rfind('-')
            else:
                split = loc.rfind('+')
            try:
                lat = float(loc[:split])
                lon = float(loc[split:])
                if lat > 90 or lat < -90:
                    self.invalid_command('Incorrect latittude')
                if lon > 180 or lon < -180:
                    self.invalid_command('Incorrect longitude')
                return [lat, lon]
            except ValueError as exc:
                self.invalid_command('Could not convert'.format(exc))

        #async def get_locations(self, loc, radius):
        #    API = 'AIzaSyBsOW1LyfxvB5cNMfQBcd3yh9EoZ9pSonk'
        #    location = self.parsed_location(loc)
        #    lat = location[0]
        #    lon = location[1]
        #    url = 'https://maps.googleapis.com/maps/api/place/nearbysearch/json?location={},{}&radius={}&key={}'.format(lat, lon, radius, API)
        #    async with aiohttp.ClientSession() as session:
        #        async with session.get(url) as response:
        #            response = await response.read()
        #            return response

        async def get_locations(self, loc, radius):
            API = 'AIzaSyBsOW1LyfxvB5cNMfQBcd3yh9EoZ9pSonk'
            location = self.parsed_location(loc)
            lat = location[0]
            lon = location[1]
            uri = '/maps/api/place/nearbysearch/json?location={},{}&radius={}&key={}'.format(lat, lon, radius, API)
            message = ('GET {} HTTP/1.1\r\n'
            'Host: maps.googleapis.com\r\n'
            'Content-Type: text/plain; charset=utf-8\r\n'
            'Connection: close'
            '\r\n'
            '\r\n').format(uri)
            try:
                reader, writer = await asyncio.open_connection('maps.googleapis.com', 443, loop=self.server_protocol.loop, ssl=True)
                print('Connected to Google Places API')
                writer.write(message.encode('utf-8'))
                response = await reader.read()
                print('Data received')
                response = response.decode()
                first = response.index('{')
                second = response.rindex('}') + 1
                logging.info(response[first:second])
                return response[first:second]
            except Exception as exc:
                print("Whoops, looks like something went wrong: ".format(exc))
                self.invalid_command(exc)


        async def iamat_message(self, data):
            if len(data) < 4:
                self.invalid_command('Incorrect number of parameters')
            clientid = no_wsp(data[1])
            location = no_wsp(data[2])
            timestamp = float(no_wsp(data[3]))
            time_diff = time.time() - timestamp
            message = ''
            if time_diff > 0:
                message += ('AT {} +{} {} {} {}'.format(self.server_protocol.server_id, time_diff, clientid, location, timestamp))
                self.server_protocol.clients[clientid] = message
            else:
                message += ('AT {} {} {} {} {}'.format(self.server_protocol.server_id, time_diff, clientid, location, timestamp))
                self.server_protocol.clients[clientid] = message
            try:
                modded_message = message + ' ' + clientid + ' ' + self.server_protocol.server_id
                await self.notify_the_neighbors(modded_message, self.server_protocol.neighbors)
                self.transport.write(message.encode())
            except ConnectionRefusedError as exc:
                response = ('The following error occurred: {}'.format(exc))
                self.transport.write(response.encode())
            self.transport.close()

        def process_json(self, response, limit):
            data = json.loads(response)
            result = data['results']
            result = result[:limit]
            data['results'] = result
            message = '{}\n\n'.format(json.dumps(data, indent=4))
            return message

        async def notify_the_neighbors(self, message, neighbors):
            for i in neighbors:
                try:
                    reader, writer = await asyncio.open_connection(HOST, PORT[i], loop=self.server_protocol.loop)
                    print('Sending AT message to {}'.format(i))
                    writer.write(message.encode())
                    #data = await reader.read(-1)
                    writer.close()
                except ConnectionRefusedError:
                    print("{} not available. Try again later.".format(i))


        async def at_message(self, data):
            if len(data) < 8:
                self.invalid_command('Incorrect number of parameters')
            else:
                size = len(data)
                message = data[0:size - 2]
                client = data[size - 2]
                server_id = data[size - 1]
                if data[1] == self.server_protocol.server_id:
                    print('Message already received')
                else:
                    self.server_protocol.clients[client] = ' '.join(message)
                    self.transport.write('Following data received: '.format(message).encode())
                    if server_id in self.server_protocol.neighbors:
                        neighbors = list(self.server_protocol.neighbors)
                        neighbors.remove(server_id)
                        data[size - 1] = self.server_protocol.server_id
                        await self.notify_the_neighbors(' '.join(data), neighbors)
                    else:
                        data[size - 1] = self.server_protocol.server_id
                        await self.notify_the_neighbors(' '.join(data), self.server_protocol.neighbors)

            self.transport.close()


        async def whatsat_message(self, data):
            if len(data) < 4:
                self.invalid_command('Incorrect number of parameters')
            clientid = no_wsp(data[1])
            radius = float(no_wsp(data[2]))
            max_places = int(no_wsp(data[3]))
            if radius <= 50 and max_places <= 20:

                if clientid not in self.server_protocol.clients:
                    return self.invalid_command("{} not found.".format(clientid))

                details = self.server_protocol.clients[clientid].split(' ')
                location = details[4]
                radius *= 1000

                google_response = await self.get_locations(location, radius)
                response = self.process_json(google_response, max_places)
                final_response = '{}\n{}'.format(self.server_protocol.clients[clientid], response)
                print(final_response)
                logging.info(final_response)
                self.transport.write(final_response.encode('utf-8'))
            else:
                response = incorrect_input()
                self.transport.write(response.encode('utf-8'))
            self.transport.close()


    def __init__(self, server_id, port, loop):
        self.server_id = server_id
        self.clients = {}
        self.server = loop.create_server(lambda: self.ServerProtocol(self), HOST, PORT[server_id])
        self.neighbors = NEIGHBORS[server_id]
        self.loop = loop

def main():
    if len(sys.argv) != 2:
        sys.stderr.write('Enter name of server to continue..')
        exit(1)
    serverName = sys.argv[1]
    if serverName not in SERVERS:
        sys.stderr.write('Not a valid server')
        exit(1)
    loop = asyncio.get_event_loop()
    proxy_server = Server(serverName, PORT[serverName], loop)
    logging.basicConfig(filename='{}.log'.format(serverName), level=logging.INFO)
    servers = loop.run_until_complete(proxy_server.server)
    print('Serving on {}'.format(servers.sockets[0].getsockname()))
    try:
        loop.run_forever()
    except KeyboardInterrupt:
        servers.close()

    loop.close()

if __name__ == '__main__':
    main()
