FROM python:3.9-slim

# Set the working directory
WORKDIR /smsapp/

# Copy the current directory contents into the container
COPY requirements.txt /smsapp/

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the current directory contents into the container at /smsapp/
COPY . .

# Expose port 6000 to the outside world
EXPOSE 7000

# Run app.py when the container launches
CMD ["python", "app.py"]
